# ADR-020 — Geospatial Storage Strategy

**Status:** Accepted (Phase 3)

## Decision (D2 = Option A, PostGIS-ready)
Use **plain PostgreSQL** for all Phase 3 geometry. No PostGIS, no GeoDjango.

- **Points** (city center, camera/intersection/segment/camera locations): two
  `DecimalField(max_digits=9, decimal_places=6)` columns `*_lat` / `*_lng` (WGS84).
- **Lines / polygons** (segment/lane geo geometry; ROI/line/stop image geometry):
  a `JSONField` storing `{"space": "<coordinate_space>", "coordinates": [[a,b], …]}`
  in **GeoJSON coordinate order** (`[lng,lat]` for geo, `[x,y]` for normalized image).

## Rationale
- PostGIS is **not installed** on this PostgreSQL 18 (`pg_available_extensions`
  has no `postgis`); adopting it needs PostGIS + GEOS/GDAL/PROJ + GeoDjango on
  Windows (heavy, brittle) and `CREATE EXTENSION` privilege.
- Phase 3 is configuration CRUD with no spatial-index/point-in-polygon hot path.
- Storing coordinates in GeoJSON order keeps a **mechanical** future migration
  (`ST_GeomFromGeoJSON`) open.

## Future PostGIS trigger
Adopt PostGIS when spatial querying becomes hot — expected at digital-twin /
simulation / routing / large-network point-in-polygon. At that point install the
extension, add `geometry`/`geography` columns, backfill from the stored GeoJSON,
and add spatial (GiST) indexes.

## Validation (this phase)
`common.geometry` validators enforce lat/lng ranges, normalized [0,1] ranges,
polygon min-vertices, non-degenerate lines, duplicate-point rejection, vertex
caps, and coordinate-space match. See ADR/plan §19.
