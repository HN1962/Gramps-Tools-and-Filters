# -*- coding: utf-8 -*-
#
# filterengine.py — den GUI-fri "motor" bag filter-byggeren.
#
# Ansvar (alt bevist i tidligere smaa tests, her samlet og haerdet):
#   * Lager: hoved- og temp-filtre i EEN fil, to sektioner
#     {"main":[...], "temp":[...]}. Referencer paa STABILT id.
#   * CRUD: create / get / list / update / rename / delete.
#   * Referentiel integritet: who_uses, dangling_refs, find_cycles.
#     delete() blokerer hvis filteret stadig er i brug.
#   * Palette: hele Gramps' person-regelliste (editor_rule_list) +
#     detektion af hvilke regel-argumenter der er filter-referencer.
#   * Koersel:
#       - preview(fid): kortlivet flash-temp (registrer -> apply -> fjern),
#         roerer aldrig custom_filters.xml.
#       - apply_to_view(fid, view): skubber filteret til HOVEDVISNINGEN og
#         holder de refererede temp-filtre registreret i den in-memory
#         CustomFilters INDTIL reset_view(), fordi visningen genberegner
#         filteret senere (redigering, db-aendringer, goto).
#       - reset_view(view): fjerner visningens filter og rydder de
#         tilbageholdte koere-filtre op.
#
# Toppen importerer KUN stdlib, saa modulet kan importeres og graf-logikken
# testes uden et koerende Gramps. Alt gramps-specifikt importeres dovent.

import os
import json
import uuid
import tempfile

KINDS = ("main", "temp")
OPS = ("and", "or", "one")      # logiske operatorer, jf. GenericFilter
RUN_PREFIX = "__flow_"          # praefiks paa vores midlertidige koere-filtre
FILTER_LABEL = "Filter name:"   # Gramps-label der markerer et filter-argument

# Proces-globalt: de koere-filtre der LIGE NU er pushet til en visning, paa
# tvaers af ALLE FilterEngine-instanser (byggevindue OG gramplet deler samme
# in-memory CustomFilters). En instans tracker kun SINE egne i
# ``_view_run_filters``; lukkes vinduet, doer den liste, men objekterne bliver
# haengende i CustomFilters til genstart. Dette saet lader ``sweep_orphans()``
# skelne "stadig i brug" (spring over) fra "efterladt lig" (fjern).
_LIVE_RUN_FILTERS = set()


# ---------------------------------------------------------------------------
# Smaa UI-praeferencer (paned-deler + kolonne-bredder) i en sidecar ``ui.json``.
# Ligger paa VERSION_DIR-niveau (IKKE per-trae), saa layout foelger brugeren paa
# tvaers af slaegtsboeger. Bevidst adskilt fra vindues-geometrien (setup_configs).
# Bor her i datalaget saa baade ruleeditor og byggevinduet deler ÉN kilde.
# ---------------------------------------------------------------------------
def ui_prefs_path():
    from gramps.gen.const import VERSION_DIR
    d = os.path.join(VERSION_DIR, "filterbuilder")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return os.path.join(d, "ui.json")


def load_ui_prefs():
    try:
        with open(ui_prefs_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_ui_pref(key, value):
    prefs = load_ui_prefs()
    prefs[key] = value
    path = ui_prefs_path()
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(prefs, fh)
        os.replace(tmp, path)          # atomisk
    except Exception:
        pass


def make_quiet_user(dbstate=None, uistate=None):
    """En gen-User der ALDRIG popper dialoger eller printer, men stadig baerer
    uistate/dbstate.

    Hvorfor: filter-regler kalder ``user.warn(...)`` / fremskridts-metoder under
    ``prepare(db, user)``. Kalder vi ``filter.apply(db)`` UDEN user, er user
    ``None`` og enhver saadan regel crasher (fx "aktiv person"-reglen:
    ``AttributeError: 'NoneType' object has no attribute 'warn'``). Det tomme
    live-tal var samme aarsag: optaellingen fejlede stille.

    Ved at give et lydloest user med:
      * crasher ingen regel laengere (warn/progress er no-ops),
      * kan regler der har brug for den AKTIVE person naa den via ``user.uistate``
        (derfor traader byggevinduet sit rigtige uistate ind her),
      * popper der INGEN advarselsdialoger op ved hver debounced optaelling.
    """
    from gramps.gen.user import User as _User

    class _QuietUser(_User):
        def warn(self, *a, **k):
            pass

        def notify_error(self, *a, **k):
            pass

        def notify_db_error(self, *a, **k):
            pass

        def notify_db_repair(self, *a, **k):
            pass

        def begin_progress(self, *a, **k):
            pass

        def step_progress(self, *a, **k):
            pass

        def end_progress(self, *a, **k):
            pass

        def info(self, *a, **k):
            pass

    try:
        return _QuietUser(uistate=uistate, dbstate=dbstate)
    except Exception:
        return _QuietUser()


# =====================================================================
# Rene datahjaelpere (ingen Gramps) — nemme at teste isoleret
# =====================================================================

def _new_id():
    return "flt_" + uuid.uuid4().hex[:10]


class FilterEngine:
    def __init__(self, dbstate=None, namespace="Person", store_path=None):
        self.dbstate = dbstate
        self.namespace = namespace
        self._store_path = store_path
        self._store = {"main": [], "temp": []}
        self._palette = None                 # bygges dovent
        self._view_run_filters = []          # gf'er registreret til aktiv view-push

    # ----------------------------------------------------------------
    # Persistence (EEN fil, atomisk skrivning)
    # ----------------------------------------------------------------
    def _tree_meta(self):
        """(id, name) for det aktive traeet. id = stabilt mappenavn
        (get_dbid), som overlever omdoebning; name = det laesbare navn."""
        db = getattr(self.dbstate, "db", None) if self.dbstate else None
        tid, tname = "", ""
        if db is not None:
            try:
                tid = db.get_dbid() or ""
            except Exception:
                tid = ""
            try:
                tname = db.get_dbname() or ""
            except Exception:
                tname = ""
        return tid, tname

    def _base_dir(self):
        from gramps.gen.const import VERSION_DIR
        return os.path.join(VERSION_DIR, "filterbuilder")

    def base_dir(self):
        """Vores per-traeet mappe (til fil-dialogers startmappe)."""
        return self._base_dir()

    def _legacy_path(self):
        """Den gamle, app-brede fil (foer per-traeet-lageret)."""
        from gramps.gen.const import VERSION_DIR
        return os.path.join(VERSION_DIR, "flow_filters.json")

    def path(self):
        """Per-traeet fil: <VERSION_DIR>/filterbuilder/<dbid>.json.

        Filnavnet er traeets STABILE id (mappenavn), saa det rette traeet altid
        faar sine egne filtre og en omdoebning ikke forvirrer noget. Traeets
        laesbare navn gemmes INDE i filen (se save). Er der intet id (ingen db
        aaben), bruges et neutralt navn, saa intet skrives oveni et rigtigt traes
        fil. En eksplicit store_path (tests) vinder altid.
        """
        if self._store_path:
            return self._store_path
        tid, _tname = self._tree_meta()
        fname = ("%s.json" % tid) if tid else "_no_tree.json"
        return os.path.join(self._base_dir(), fname)

    def _read_file(self, p):
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return {"main": data.get("main", []), "temp": data.get("temp", [])}

    def _normalize_loaded(self):
        for _kind, flt in self.all():
            flt.setdefault("op", "and")
            flt.setdefault("invert", False)
            flt.setdefault("comment", "")
            flt.setdefault("rules", [])

    def load(self):
        p = self.path()
        if os.path.isfile(p):
            self._store = self._read_file(p)
        elif not self._store_path and os.path.isfile(self._legacy_path()):
            # EEN-gangs faldback: den gamle app-brede fil laeses ind saa
            # eksisterende arbejde ikke gaar tabt. Vi skriver IKKE her (kun paa
            # Save) og sletter ikke den gamle fil. Foerste Save skriver den nye
            # per-traeet fil; derefter kan du roligt slette flow_filters.json.
            self._store = self._read_file(self._legacy_path())
        else:
            self._store = {"main": [], "temp": []}
        self._normalize_loaded()
        return self._store

    def _dump(self, p, store):
        """Atomisk skriv af 'store' (+ traeets navn) til p."""
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tid, tname = self._tree_meta()
        payload = {"tree": {"id": tid, "name": tname},
                   "main": store.get("main", []),
                   "temp": store.get("temp", [])}
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, p)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def save(self):
        self._dump(self.path(), self._store)

    # ----------------------------------------------------------------
    # Hel-fil Import/Eksport (til at flytte filtre mellem traeer)
    # ----------------------------------------------------------------
    def export_to(self, filepath):
        """Skriv DETTE traes filtre til en valgfri (pænt navngivet) fil."""
        self._dump(filepath, self._store)
        return filepath

    def file_info(self, filepath):
        """Kig i en fil UDEN at importere: hvem/hvor mange.

        Returnerer {"id","name","main","temp"} fra filens "tree"-sektion og
        antal filtre, saa dialogen kan vise 'fra «Slægt A»' foer man erstatter.
        """
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        tree = data.get("tree", {}) or {}
        return {"id": tree.get("id", ""), "name": tree.get("name", ""),
                "main": len(data.get("main", [])),
                "temp": len(data.get("temp", []))}

    def import_from(self, filepath):
        """Erstat dette traes filtre (i hukommelsen) med filens indhold.

        Hel-fil: alt fra filen bliver dette traes filtre. Skriver IKKE til
        disk selv — kalderen (byggevinduet) gemmer bagefter, saa diskskrivning
        stadig kun sker paa Save. Returnerer (antal_main, antal_temp).
        """
        loaded = self._read_file(filepath)
        self._store = {"main": list(loaded.get("main", [])),
                       "temp": list(loaded.get("temp", []))}
        self._normalize_loaded()
        return len(self._store["main"]), len(self._store["temp"])

    def _filter_signature(self, flt, get_by_id, seen=None):
        """Struktur-signatur der er UAFHAENGIG af id'er.

        To filtre er "det samme" hvis de har samme op/invert og samme regler,
        hvor en filter-REFERENCE sammenlignes paa det refererede filters egen
        signatur (rekursivt) — ikke paa dets id. Saa et hjaelpefilter der HEDDER
        det samme men INDEHOLDER noget andet faar en ANDEN signatur (og bliver
        derfor ikke fejlagtigt slaaet sammen under import). Cyklus-sikret.
        """
        if seen is None:
            seen = set()
        fid = flt.get("id")
        if fid in seen:
            return ("CYCLE",)
        seen = seen | {fid}
        rule_sigs = []
        for rule in flt.get("rules", []):
            refs = set(rule.get("filter_refs", []))
            vals = []
            for v in rule.get("values", []):
                if v in refs:
                    child = get_by_id(v)
                    if child is None:
                        vals.append(("REF_MISSING", v))
                    else:
                        vals.append(
                            ("REF",
                             self._filter_signature(child, get_by_id, seen)))
                else:
                    vals.append(("LIT", v))
            rule_sigs.append((rule.get("class"), tuple(vals),
                              bool(rule.get("use_regex", False)),
                              bool(rule.get("use_case", False))))
        return (flt.get("op", "and"), bool(flt.get("invert", False)),
                tuple(rule_sigs))

    def merge_from(self, filepath, apply=True):
        """Merge a file's filters INTO this tree instead of replacing them, so
        nothing is lost. Deduplication is by CONTENT, not by name:

          * An incoming filter whose CONTENT already exists here (same kind,
            regardless of its name) is a true duplicate -> skipped, and any
            reference to it is redirected to the local one. This keeps repeated
            imports idempotent (they add 0).
          * An incoming filter whose NAME clashes with a local filter that has
            DIFFERENT content is NOT the same filter. It is added under a fresh,
            non-clashing name ("Name (2)", "Name (3)", ...). Crucially, an
            incoming MAIN filter that referenced that helper is rewired to the
            newly added (correct) helper -- not to the local same-name one.
            This closes the "same helper name, different meaning" trap where an
            imported main would otherwise silently point at the wrong helper.
          * Everything else is added under its own name with a fresh id.

        References survive: each added filter's `values`/`filter_refs` are
        rewritten through an id remap. Returns
        {"added_main", "added_temp", "skipped": [names], "renamed": [(old,new)]}.
        With apply=False it computes the same summary WITHOUT changing anything.
        Does not write to disk; the caller saves.
        """
        loaded = self._read_file(filepath)
        incoming = {"main": list(loaded.get("main", [])),
                    "temp": list(loaded.get("temp", []))}

        # id -> dict, within each side, so signatures can resolve references.
        incoming_by_id = {}
        for kind in KINDS:
            for f in incoming[kind]:
                incoming_by_id[f["id"]] = f
        inc_get = incoming_by_id.get

        local_by_id = {}
        for kind in KINDS:
            for f in self._store[kind]:
                local_by_id[f["id"]] = f
        loc_get = local_by_id.get

        # Existing local filters indexed by content-signature and by name.
        sig_to_local = {"main": {}, "temp": {}}
        name_to_id = {}
        for kind in KINDS:
            for f in self._store[kind]:
                sig_to_local[kind].setdefault(
                    self._filter_signature(f, loc_get), f["id"])
                name_to_id[(kind, (f.get("name") or "").strip().lower())] = \
                    f["id"]

        remap = {}                       # incoming id -> effective id
        to_add = {"main": [], "temp": []}
        skipped = []                     # names of true content-duplicates
        renamed = []                     # (original name, new name)

        # Helpers (temp) before mains, so a main's helper already has an id/name.
        for kind in ("temp", "main"):
            for f in incoming[kind]:
                sig = self._filter_signature(f, inc_get)
                if sig in sig_to_local[kind]:
                    remap[f["id"]] = sig_to_local[kind][sig]   # already here
                    skipped.append((f.get("name") or "").strip())
                    continue
                orig = (f.get("name") or "").strip()
                name, n = orig, 2
                while (kind, name.lower()) in name_to_id:
                    name = "%s (%d)" % (orig, n)
                    n += 1
                new_id = _new_id()
                remap[f["id"]] = new_id
                name_to_id[(kind, name.lower())] = new_id
                sig_to_local[kind][sig] = new_id
                nf = dict(f)
                nf["id"] = new_id
                nf["name"] = name
                if name != orig:
                    renamed.append((orig, name))
                to_add[kind].append(nf)

        if apply:
            for kind in ("temp", "main"):
                for nf in to_add[kind]:
                    new_rules = []
                    for r in nf.get("rules", []):
                        r = dict(r)
                        if "values" in r:
                            r["values"] = [remap.get(v, v) for v in r["values"]]
                        if "filter_refs" in r:
                            r["filter_refs"] = [remap.get(v, v)
                                                for v in r["filter_refs"]]
                        new_rules.append(r)
                    nf["rules"] = new_rules
                    self._store[kind].append(nf)
            self._normalize_loaded()

        return {"added_main": len(to_add["main"]),
                "added_temp": len(to_add["temp"]),
                "skipped": skipped,
                "renamed": renamed}

    def scan_rule_classes(self, filepath):
        """Alle regel-KLASSE-navne der bruges i en fil (uden at importere).

        Ren/headless: laeser kun JSON. Bruges til at advare om regler der ikke
        findes i denne Gramps foer man importerer.
        """
        loaded = self._read_file(filepath)
        classes = set()
        for kind in KINDS:
            for f in loaded.get(kind, []):
                for r in f.get("rules", []):
                    c = r.get("class")
                    if c:
                        classes.add(c)
        return classes

    def missing_rules(self, filepath):
        """Regel-klasser i filen som IKKE findes i denne Gramps' palette.

        Kraever Gramps indlaest (palette()). Returnerer en sorteret liste; tom
        liste betyder at alle noedvendige regler er tilgaengelige her.
        """
        known = set(self.palette().keys())
        return sorted(self.scan_rule_classes(filepath) - known)

    # ----------------------------------------------------------------
    # Opslag
    # ----------------------------------------------------------------
    def list(self, kind):
        if kind not in KINDS:
            raise ValueError("Ukendt type: %s" % kind)
        return list(self._store.get(kind, []))

    def all(self):
        for kind in KINDS:
            for flt in self._store.get(kind, []):
                yield kind, flt

    def get(self, fid):
        for _kind, flt in self.all():
            if flt["id"] == fid:
                return flt
        return None

    def name_exists(self, name, kind=None):
        for k, flt in self.all():
            if flt["name"] == name and (kind is None or k == kind):
                return True
        return False

    # ----------------------------------------------------------------
    # CRUD
    # ----------------------------------------------------------------
    def create(self, kind, name, rules, comment="", op="and", invert=False):
        if kind not in KINDS:
            raise ValueError("Ukendt type: %s" % kind)
        self._check_op(op)
        rules = self._clean_rules(rules)
        self._check_refs_exist(rules)
        fid = _new_id()
        self._store[kind].append({
            "id": fid, "kind": kind, "name": name,
            "comment": comment, "op": op, "invert": bool(invert),
            "rules": rules,
        })
        return fid

    def update(self, fid, name=None, rules=None, comment=None,
               op=None, invert=None):
        flt = self.get(fid)
        if flt is None:
            raise ValueError("Ukendt filter-id: %s" % fid)
        if name is not None:
            flt["name"] = name
        if comment is not None:
            flt["comment"] = comment
        if op is not None:
            self._check_op(op)
            flt["op"] = op
        if invert is not None:
            flt["invert"] = bool(invert)
        if rules is not None:
            rules = self._clean_rules(rules)
            self._check_refs_exist(rules, exclude=fid)
            flt["rules"] = rules
            if self.find_cycles():
                # rul tilbage hvis opdateringen skabte en cyklus
                raise ValueError("Opdateringen ville skabe en cyklisk reference")
        return flt

    def rename(self, fid, new_name):
        return self.update(fid, name=new_name)

    def delete(self, fid):
        """Returnerer (ok, users). Blokerer hvis filteret stadig er i brug."""
        flt = self.get(fid)
        if flt is None:
            return False, ["(findes ikke)"]
        users = self.who_uses(fid)
        if users:
            return False, users
        self._store[flt["kind"]].remove(flt)
        return True, []

    # ----------------------------------------------------------------
    # Referentiel integritet (ren graf-logik, ingen Gramps)
    # ----------------------------------------------------------------
    def who_uses(self, fid):
        """Navne paa filtre (uanset type) der refererer fid."""
        users = []
        for _kind, flt in self.all():
            if flt["id"] == fid:
                continue
            for rule in flt.get("rules", []):
                if fid in rule.get("filter_refs", []):
                    users.append(flt["name"])
                    break
        return users

    def dangling_refs(self):
        """Liste af (filter-id, manglende-ref-id) hvor en ref ikke findes."""
        ids = {flt["id"] for _k, flt in self.all()}
        bad = []
        for _kind, flt in self.all():
            for rule in flt.get("rules", []):
                for ref in rule.get("filter_refs", []):
                    if ref not in ids:
                        bad.append((flt["id"], ref))
        return bad

    def find_cycles(self):
        """True hvis referencegrafen indeholder mindst een cyklus."""
        graph = {}
        for _kind, flt in self.all():
            outgoing = set()
            for rule in flt.get("rules", []):
                outgoing.update(rule.get("filter_refs", []))
            graph[flt["id"]] = outgoing

        WHITE, GREY, BLACK = 0, 1, 2
        color = {node: WHITE for node in graph}

        def visit(node):
            color[node] = GREY
            for nxt in graph.get(node, ()):
                if nxt not in color:
                    continue  # dangling haandteres separat
                if color[nxt] == GREY:
                    return True
                if color[nxt] == WHITE and visit(nxt):
                    return True
            color[node] = BLACK
            return False

        return any(color[n] == WHITE and visit(n) for n in graph)

    # ----------------------------------------------------------------
    # Palette (Gramps' egne person-regler) — doven import
    # ----------------------------------------------------------------
    def palette(self):
        if self._palette is None:
            if self.namespace != "Person":
                raise NotImplementedError(
                    "Kun 'Person'-paletten er tilsluttet indtil videre")
            from gramps.gen.filters.rules.person import editor_rule_list
            self._palette = {cls.__name__: cls for cls in editor_rule_list}
        return self._palette

    def rule_filter_arg_indexes(self, class_name):
        """Positioner i en regels argumentliste der er filter-referencer.

        Bruges af byg-dialogen: naar en regel har et 'Filter name:'-argument,
        skal vaerdien vaelges fra vores to filterlister og id'et lagres i
        baade values[i] og filter_refs.
        """
        cls = self.palette().get(class_name)
        if cls is None:
            raise ValueError("Ukendt regel: %s" % class_name)
        from gramps.gen.const import GRAMPS_LOCALE as glocale
        target = glocale.translation.gettext(FILTER_LABEL)
        labels = getattr(cls, "labels", []) or []
        return [i for i, lab in enumerate(labels) if lab == target]

    # ----------------------------------------------------------------
    # Koersel: compileren id -> koerenavn (doven Gramps-import)
    # ----------------------------------------------------------------
    def _custom(self):
        import gramps.gen.filters as gfilt
        if gfilt.CustomFilters is None:
            raise RuntimeError("CustomFilters er ikke indlaest (ingen db aaben?)")
        return gfilt.CustomFilters

    def _materialize(self, fid, registered, in_progress, custom):
        """Byg GenericFilter for fid, registrer under koerenavn, returner navnet.

        Rekursiv, cyklus-sikker. Skriver kun til den in-memory CustomFilters.
        """
        if fid in registered:
            return registered[fid][0]
        if fid in in_progress:
            raise ValueError("Cyklisk reference via %s" % fid)
        flt = self.get(fid)
        if flt is None:
            raise ValueError("Ukendt filter-id: %s" % fid)

        from gramps.gen.filters import GenericFilterFactory
        in_progress.add(fid)
        gfilter = GenericFilterFactory(self.namespace)()
        run_name = "%s%s_%s" % (RUN_PREFIX, fid, uuid.uuid4().hex[:8])
        gfilter.set_name(run_name)

        palette = self.palette()
        for rule in flt.get("rules", []):
            values = list(rule.get("values", []))
            for ref_id in rule.get("filter_refs", []):
                child_run = self._materialize(ref_id, registered, in_progress, custom)
                values = [child_run if v == ref_id else v for v in values]
            cls = palette.get(rule["class"])
            if cls is None:
                raise ValueError("Regel ikke i paletten: %s" % rule["class"])
            gfilter.add_rule(self._make_rule(cls, values, rule))

        # logisk operator + invertér — pr. filter (ogsaa for nestede hjaelpefiltre)
        gfilter.set_logical_op(flt.get("op", "and"))
        gfilter.set_invert(bool(flt.get("invert", False)))

        custom.add(self.namespace, gfilter)
        registered[fid] = (run_name, gfilter)
        in_progress.discard(fid)
        return run_name

    @staticmethod
    def _make_rule(cls, values, rule):
        """Instantier en Gramps-regel med evt. regex/case-flag.

        Flagene baeres KUN naar reglen faktisk har dem sat (opt-in), saa
        alle almindelige regler bygges praecis som foer: ``cls(values)``.
        Naar regex er sat, forsoeges ``use_regex``/``use_case`` -- men
        degraderer paent paa aeldre Gramps (5.2) hvor en regel-``__init__``
        maaske ikke tager ``use_case`` (eller ingen af dem): saa falder vi
        tilbage trin for trin. Gramps' Rule-basis tager
        ``__init__(self, arg, use_regex=False, use_case=False)``.
        """
        if not rule.get("use_regex"):
            return cls(values)                       # uaendret adfaerd
        use_case = bool(rule.get("use_case"))
        try:
            return cls(values, use_regex=True, use_case=use_case)
        except TypeError:
            pass
        try:
            return cls(values, use_regex=True)       # 5.2 uden use_case
        except TypeError:
            return cls(values)                       # regel uden regex-signatur

    def _remove_run_filters(self, custom, gflist):
        plist = custom.filter_namespaces.get(self.namespace, [])
        for gf in gflist:
            try:
                plist.remove(gf)
            except ValueError:
                pass

    def preview(self, fid, user=None):
        """Kortlivet koersel. Returnerer liste af handles. Rydder ALT op."""
        db = self.dbstate.db
        if user is None:
            user = make_quiet_user(dbstate=self.dbstate)
        custom = self._custom()
        registered = {}
        in_progress = set()
        try:
            self._materialize(fid, registered, in_progress, custom)
            top_gf = registered[fid][1]
            custom._cached = {}
            results = top_gf.apply(db, user=user)
        finally:
            self._remove_run_filters(
                custom, [gf for (_rn, gf) in registered.values()])
            custom._cached = {}
        return results

    def preview_rules(self, rules, op="and", invert=False, user=None):
        """Kortlivet optaelling af et UGEMT build (til live-tallet).

        Bygger en ad-hoc top-filter direkte fra (rules, op, invert). Hjaelpe-
        referencer i reglerne materialiseres fra hukommelses-lageret praecis
        som ellers. Kraever hverken gemt id eller navn, og roerer ALDRIG disken.
        Returnerer liste af handles; rydder alle koere-filtre op bagefter.
        ``user`` gives videre til apply() saa regler der taler til user (fx
        "aktiv person") ikke crasher; None -> et lydloest fallback-user.
        """
        db = self.dbstate.db
        if db is None:
            raise RuntimeError("Ingen database aaben")
        if user is None:
            user = make_quiet_user(dbstate=self.dbstate)
        from gramps.gen.filters import GenericFilterFactory
        custom = self._custom()
        registered = {}
        in_progress = set()
        try:
            top = GenericFilterFactory(self.namespace)()
            palette = self.palette()
            for rule in (rules or []):
                values = list(rule.get("values", []))
                for ref_id in rule.get("filter_refs", []):
                    child_run = self._materialize(
                        ref_id, registered, in_progress, custom)
                    values = [child_run if v == ref_id else v for v in values]
                cls = palette.get(rule.get("class"))
                if cls is None:
                    raise ValueError(
                        "Regel ikke i paletten: %s" % rule.get("class"))
                top.add_rule(cls(values))
            top.set_logical_op(op if op in OPS else "and")
            top.set_invert(bool(invert))
            custom._cached = {}
            results = top.apply(db, user=user)
        finally:
            # top-filteret registreres aldrig; kun boernene skal fjernes
            self._remove_run_filters(
                custom, [gf for (_rn, gf) in registered.values()])
            custom._cached = {}
        return results

    def apply_to_view(self, fid, view):
        """Skub filteret til hovedvisningen. Beholder koere-filtre indtil reset."""
        if view is None or not hasattr(view, "generic_filter"):
            raise RuntimeError("Kan ikke naa hovedvisningen")
        custom = self._custom()
        self._clear_view_run_filters(custom)     # ryd tidligere push
        registered = {}
        in_progress = set()
        self._materialize(fid, registered, in_progress, custom)
        top_gf = registered[fid][1]
        # Giv TOP-filteret et LAESBART navn. Saa laenge det er anvendt paa
        # person-visningen ligger det i den in-memory CustomFilters og er
        # dermed synligt/valgbart i ALLE andre Gramps person-filter-vaelgere
        # (GEDCOM-eksport, rapporter, sidepanelet). Hjaelpe-filtrene beholder
        # deres tekniske __flow_-navn (de skal blot kunne slaas op af top'ens
        # referencer; de er ikke ment til at vaelges af brugeren).
        top_gf.set_name(self._view_display_name(fid, custom, registered))
        custom._cached = {}
        view.generic_filter = top_gf
        view.build_tree()
        # BEHOLD registreringerne — visningen genberegner filteret senere.
        self._set_view_run_filters([gf for (_rn, gf) in registered.values()])

    def _view_display_name(self, fid, custom, registered):
        """Laesbart, kollisions-sikkert navn til det anvendte top-filter.

        Grundnavn = filterets eget navn (det brugeren ser i EFB). Er der
        allerede et FREMMED filter (ikke et af vores __flow_-koere-filtre) med
        praecis det navn i CustomFilters, tilfoejes " (2)", " (3)", ... saa vi
        aldrig skaber en tvetydig dublet i de andre vaelgere.
        """
        flt = self.get(fid) or {}
        base = (flt.get("name") or "").strip() or "Filter"
        base = "wb_" + base                    # skiller sig ud i de andre vaelgere
        ours = {gf for (_rn, gf) in registered.values()}
        ours |= set(self._view_run_filters)
        taken = set()
        for gf in custom.filter_namespaces.get(self.namespace, []):
            if gf in ours:
                continue                       # vores egne koere-filtre
            nm = gf.get_name() or ""
            if nm.startswith(RUN_PREFIX):
                continue                       # en efterladt __flow_ (usandsynligt)
            taken.add(nm)
        name, n = base, 2
        while name in taken:
            name = "%s (%d)" % (base, n)
            n += 1
        return name

    def apply_rules_to_view(self, rules, op="and", invert=False, view=None,
                            user=None):
        """Skub et UGEMT build (rules, op, invert) til hovedvisningen.

        Som apply_to_view, men top-filteret bygges ad-hoc fra reglerne (praecis
        som preview_rules) i stedet for fra et gemt id. Hjaelpe-referencer
        materialiseres fra hukommelses-lageret og BEHOLDES registreret indtil
        reset_view(), fordi visningen genberegner filteret senere. Top-filteret
        registreres aldrig i CustomFilters; visningen holder selv referencen.
        Returnerer (top_gf, antal-matches). Matcher det live-tallet viser, fordi
        begge gaar gennem samme regel-kompilering. ``user`` bruges til vores
        pre-optaelling (selve listens genberegning bruger Gramps' eget GUI-user).
        """
        if view is None or not hasattr(view, "generic_filter"):
            raise RuntimeError("Kan ikke naa hovedvisningen")
        db = self.dbstate.db
        if db is None:
            raise RuntimeError("Ingen database aaben")
        if user is None:
            user = make_quiet_user(dbstate=self.dbstate)
        from gramps.gen.filters import GenericFilterFactory
        custom = self._custom()
        self._clear_view_run_filters(custom)     # ryd tidligere push
        registered = {}
        in_progress = set()
        top = GenericFilterFactory(self.namespace)()
        palette = self.palette()
        for rule in (rules or []):
            values = list(rule.get("values", []))
            for ref_id in rule.get("filter_refs", []):
                child_run = self._materialize(
                    ref_id, registered, in_progress, custom)
                values = [child_run if v == ref_id else v for v in values]
            cls = palette.get(rule.get("class"))
            if cls is None:
                raise ValueError("Regel ikke i paletten: %s" % rule.get("class"))
            top.add_rule(cls(values))
        top.set_logical_op(op if op in OPS else "and")
        top.set_invert(bool(invert))
        custom._cached = {}
        count = len(top.apply(db, user=user))    # samme tal som live-tallet
        view.generic_filter = top
        view.build_tree()
        # BEHOLD kun boerne-registreringerne saa visningen kan genberegne.
        self._set_view_run_filters([gf for (_rn, gf) in registered.values()])
        return top, count

    def reset_view(self, view):
        custom = self._custom()
        if view is not None and hasattr(view, "generic_filter"):
            view.generic_filter = None
            view.build_tree()
        self._clear_view_run_filters(custom)

    def _set_view_run_filters(self, gflist):
        """Registrer de koere-filtre der lige er pushet til visningen — baade paa
        DENNE instans (``_view_run_filters``) OG i det proces-globale
        ``_LIVE_RUN_FILTERS``. Sidstnaevnte er det som ``sweep_orphans()`` bruger
        til at fri-holde stadig-aktive filtre paa tvaers af instanser."""
        self._view_run_filters = list(gflist)
        _LIVE_RUN_FILTERS.update(self._view_run_filters)

    def _clear_view_run_filters(self, custom):
        self._remove_run_filters(custom, self._view_run_filters)
        # ud af det globale live-saet OGSAA — ellers ville sweep_orphans tro de
        # stadig var i brug og aldrig turde fjerne dem.
        _LIVE_RUN_FILTERS.difference_update(self._view_run_filters)
        self._view_run_filters = []
        custom._cached = {}

    def cleanup(self):
        """Kald ved nedlukning/db-skift saa intet efterlades i hukommelsen."""
        try:
            custom = self._custom()
        except RuntimeError:
            _LIVE_RUN_FILTERS.difference_update(self._view_run_filters)
            self._view_run_filters = []
            return
        self._clear_view_run_filters(custom)

    def sweep_orphans(self):
        """Fjern EFTERLADTE koere-filtre (``__flow_``) fra den delte in-memory
        CustomFilters.

        Baggrund: byggevinduet og gramplet'en har HVER sin FilterEngine, men
        skriver til SAMME proces-globale CustomFilters. Lukkes byggevinduet mens
        et preview er pushet (eller skiftes traeet), doer instansens
        ``_view_run_filters``, men objekterne bliver haengende i CustomFilters og
        dukker op i ALLE person-filter-vaelgere (GEDCOM-eksport, rapporter,
        sidepanel) indtil Gramps genstartes. Det var praecis symptomet: en voksende
        bunke ``__flow_flt_...`` som hverken Reset eller traeet-luk ryddede.

        Sikkerhed:
          * Fjerner KUN filtre med ``__flow_``-praefiks -> brugerens egne (og de
            laesbare ``wb_``-anvendte top-filtre) roeres ALDRIG.
          * Springer alt over der stadig er LIVE paa en visning (ligger i
            ``_LIVE_RUN_FILTERS``) -> et aktivt preview i et andet vindue overlever.
        Returnerer antal fjernede (til diagnose/logning)."""
        try:
            custom = self._custom()
        except RuntimeError:
            return 0
        plist = custom.filter_namespaces.get(self.namespace, [])
        dead = [gf for gf in list(plist)
                if gf.get_name().startswith(RUN_PREFIX)
                and gf not in _LIVE_RUN_FILTERS]
        for gf in dead:
            try:
                plist.remove(gf)
            except ValueError:
                pass
        if dead:
            custom._cached = {}
        return len(dead)

    def has_leaked_run_filters(self):
        """Diagnose: er der '__flow_'-filtre tilbage i CustomFilters?"""
        custom = self._custom()
        plist = custom.filter_namespaces.get(self.namespace, [])
        return [f.get_name() for f in plist
                if f.get_name().startswith(RUN_PREFIX)]

    # ----------------------------------------------------------------
    # interne valideringer
    # ----------------------------------------------------------------
    def _check_op(self, op):
        if op not in OPS:
            raise ValueError(
                "Ukendt logisk operator: %r (skal vaere en af: %s)"
                % (op, ", ".join(OPS)))

    def _clean_rules(self, rules):
        clean = []
        for rule in rules:
            cr = {
                "class": rule["class"],
                "values": list(rule.get("values", [])),
                "filter_refs": list(rule.get("filter_refs", [])),
            }
            # regex/case-flag baeres KUN med naar regex er slaaet til, saa filtre
            # uden regex beholder praecis samme JSON som foer (byte-identisk).
            if rule.get("use_regex"):
                cr["use_regex"] = True
                if rule.get("use_case"):
                    cr["use_case"] = True
            clean.append(cr)
        # hver ref skal optraede i samme regels values
        for rule in clean:
            for ref in rule["filter_refs"]:
                if ref not in rule["values"]:
                    raise ValueError(
                        "filter_refs '%s' mangler i values %s"
                        % (ref, rule["values"]))
        return clean

    def _check_refs_exist(self, rules, exclude=None):
        ids = {flt["id"] for _k, flt in self.all() if flt["id"] != exclude}
        for rule in rules:
            for ref in rule.get("filter_refs", []):
                if ref not in ids:
                    raise ValueError("Reference til ukendt filter-id: %s" % ref)
