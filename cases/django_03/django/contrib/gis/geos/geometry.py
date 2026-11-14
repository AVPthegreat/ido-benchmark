inherit from this object.
"""

import re
from ctypes import addressof, byref, c_double

from django.contrib.gis import gdal
from django.contrib.gis.geometry import hex_regex, json_regex, wkt_regex
from django.contrib.gis.geos import prototypes as capi
from django.contrib.gis.geos.base import GEOSBase
from django.contrib.gis.geos.coordseq import GEOSCoordSeq
from django.contrib.gis.geos.error import GEOSException
from django.contrib.gis.geos.libgeos import GEOM_PTR, geos_version_tuple
from django.contrib.gis.geos.mutable_list import ListMixin
from django.contrib.gis.geos.prepared import PreparedGeometry
from django.contrib.gis.geos.prototypes.io import (
    MAX_GEOM_COLLECTIONS,
    ewkb_w,
    wkb_r,
    wkb_w,
    wkt_r,
    wkt_w,
)
from django.utils.deconstruct import deconstructible
from django.utils.encoding import force_bytes, force_str


class GEOSGeometryBase(GEOSBase):
    _GEOS_CLASSES = None

    ptr_type = GEOM_PTR
    destructor = capi.destroy_geom
    has_cs = False  # Only Point, LineString, LinearRing have coordinate sequences

    def __init__(self, ptr, cls):
        self._ptr = ptr

        # Setting the class type (e.g., Point, Polygon, etc.)
        if type(self) in (GEOSGeometryBase, GEOSGeometry):
            if cls is None:
                cls = self._get_geos_classes()[self.geom_typeid]
            self.__class__ = cls
        self._post_init()

    @staticmethod
    def _get_geos_classes():
        if GEOSGeometryBase._GEOS_CLASSES is None:
            # Inner imports avoid import conflicts with GEOSGeometry.
            from .collections import (
                GeometryCollection,
                MultiLineString,
                MultiPoint,
                MultiPolygon,
            )
            from .linestring import LinearRing, LineString
            from .point import Point
            from .polygon import Polygon

            GEOSGeometryBase._GEOS_CLASSES = {
                0: Point,
                1: LineString,
                2: LinearRing,
                3: Polygon,
                4: MultiPoint,
                5: MultiLineString,
                6: MultiPolygon,
                7: GeometryCollection,
            }
        return GEOSGeometryBase._GEOS_CLASSES

    def _post_init(self):
        "Perform post-initialization setup."
        # Setting the coordinate sequence for the geometry (will be None on
        # geometries that do not have coordinate sequences)
        self._cs = (
            GEOSCoordSeq(capi.get_cs(self.ptr), self.hasz) if self.has_cs else None
        )

    def __copy__(self):
        """
        Return a clone because the copy of a GEOSGeometry may contain an
        invalid pointer location if the original is garbage collected.
        """
        return self.clone()

    def __deepcopy__(self, memodict):
        """
        The `deepcopy` routine is used by the `Node` class of
        django.utils.tree; thus, the protocol routine needs to be implemented
        to return correct copies (clones) of these GEOS objects, which use C
        pointers.
        """
        return self.clone()

    def __str__(self):
        "EWKT is used for the string representation."
        return self.ewkt

    def __repr__(self):
        "Short-hand representation because WKT may be very large."
        return "<%s object at %s>" % (self.geom_type, hex(addressof(self.ptr)))

    # Pickling support
    def _to_pickle_wkb(self):
        return bytes(self.wkb)

    def _from_pickle_wkb(self, wkb):
        return wkb_r().read(memoryview(wkb))

    def __getstate__(self):
        # The pickled state is simply a tuple of the WKB (in string form)
        # and the SRID.
        return self._to_pickle_wkb(), self.srid

    def __setstate__(self, state):
        # Instantiating from the tuple state that was pickled.
        wkb, srid = state
        ptr = self._from_pickle_wkb(wkb)
        if not ptr:
            raise GEOSException("Invalid Geometry loaded from pickled state.")
        self.ptr = ptr
        self._post_init()
        self.srid = srid

    @classmethod
    def _from_wkb(cls, wkb, max_geom_collections=MAX_GEOM_COLLECTIONS):
        return wkb_r().read(wkb, max_geom_collections)

    @staticmethod
    def from_ewkt(ewkt):
        ewkt = force_bytes(ewkt)
        srid = None
        parts = ewkt.split(b";", 1)
        if len(parts) == 2:
            srid_part, wkt = parts
            match = re.match(rb"SRID=(?P<srid>\-?\d+)", srid_part)
            if not match:
                raise ValueError("EWKT has invalid SRID part.")
            srid = int(match["srid"])
        else:
            wkt = ewkt
        if not wkt:
            raise ValueError("Expected WKT but got an empty string.")
        return GEOSGeometry(GEOSGeometry._from_wkt(wkt), srid=srid)

    @staticmethod
    def _from_wkt(wkt, max_geom_collections=MAX_GEOM_COLLECTIONS):
        return wkt_r().read(wkt, max_geom_collections)

    @classmethod
    def from_gml(cls, gml_string):
        return gdal.OGRGeometry.from_gml(gml_string).geos

    # Comparison operators
    def __eq__(self, other):
        """
        Equivalence testing, a Geometry may be compared with another Geometry
        or an EWKT representation.
        """
        if isinstance(other, str):
            try:
                other = GEOSGeometry.from_ewkt(other)
            except (ValueError, GEOSException):
                return False
        return (
            isinstance(other, GEOSGeometry)
            and self.srid == other.srid
            and self.equals_exact(other)
        )

    def __hash__(self):
        return hash((self.srid, self.wkt))

    # ### Geometry set-like operations ###
    # Thanks to Sean Gillies for inspiration:
    #  http://lists.gispython.org/pipermail/community/2007-July/001034.html
    # g = g1 | g2
    def __or__(self, other):
        "Return the union of this Geometry and the other."
        return self.union(other)

    # g = g1 & g2
    def __and__(self, other):
        "Return the intersection of this Geometry and the other."
        return self.intersection(other)

    # g = g1 - g2
    def __sub__(self, other):
        "Return the difference this Geometry and the other."
