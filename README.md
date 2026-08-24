# Gramps Tools and Filters

A collection of independent filters and utility tools for Gramps.

## Filters

- Non-birth child relation V1.1.
  
  Matches people recorded as a child with a non-birth relationship
  to a parent (adopted, foster, step, etc.). Helps review that child
  relationship types are set correctly.

- Common Biological Ancestor V1.1.
  
  Matches people who share a common ancestor with a specified
  person, following only parent-child links recorded with the
  \"Birth\" child-reference type -- i.e. the biological line.
  Adopted, foster, step and sponsored relationships are excluded.

- A named place and its sub-places V1.0.
  
  Matches people who have an event whose place is the named place or
  lies within it, including every place enclosed by it, transitively
  down through the whole place hierarchy. Matching is by place name, so
  all places with that name are used as targets.

- Event in Place (or sub-place) V1.0.
  
  Matches places that are the named place or lie within it, including
  every place enclosed by it, transitively down through the whole place
  hierarchy. Matching is by place name, so all places with that name are
  used as targets.

## Tools

- Verify the Data → HTML report V1.1.
  
  Run Gramps’ built-in data checks and save the results as a sortable HTML report that can be reviewed item by item

- FilterWorkbench (Filterværksted) V1.1. 

  A Gramps gramplet for building, saving, editing, sharing and **testing** your own
  person filters — with reusable *helper filters* as building blocks. It lives in the
  **People** view sidebar and keeps its filters completely separate from Gramps' own
  filter editor list.
