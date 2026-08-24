"""Controlled vocabularies for the traffic network domain (Phase 3)."""
from __future__ import annotations

from django.db import models


class RoadType(models.TextChoices):
    MOTORWAY = "motorway", "Motorway"
    TRUNK = "trunk", "Trunk"
    PRIMARY = "primary", "Primary"
    SECONDARY = "secondary", "Secondary"
    TERTIARY = "tertiary", "Tertiary"
    RESIDENTIAL = "residential", "Residential"
    SERVICE = "service", "Service"
    OTHER = "other", "Other"


class Directionality(models.TextChoices):
    ONE_WAY = "one_way", "One-way"
    TWO_WAY = "two_way", "Two-way"


class SegmentDirection(models.TextChoices):
    FORWARD = "forward", "Forward"
    BACKWARD = "backward", "Backward"
    BOTH = "both", "Both"


class IntersectionType(models.TextChoices):
    SIGNALIZED = "signalized", "Signalized"
    UNSIGNALIZED = "unsignalized", "Unsignalized"
    ROUNDABOUT = "roundabout", "Roundabout"
    JUNCTION = "junction", "Junction"
    OTHER = "other", "Other"


class ApproachType(models.TextChoices):
    INCOMING = "incoming", "Incoming"
    OUTGOING = "outgoing", "Outgoing"
    BIDIRECTIONAL = "bidirectional", "Bidirectional"


class CardinalDirection(models.TextChoices):
    N = "N", "North"
    NE = "NE", "Northeast"
    E = "E", "East"
    SE = "SE", "Southeast"
    S = "S", "South"
    SW = "SW", "Southwest"
    W = "W", "West"
    NW = "NW", "Northwest"


class LaneType(models.TextChoices):
    GENERAL = "general", "General traffic"
    BUS = "bus", "Bus"
    BICYCLE = "bicycle", "Bicycle"
    EMERGENCY = "emergency", "Emergency"
    TURN = "turn", "Turn"
    PARKING = "parking", "Parking"
    SHOULDER = "shoulder", "Shoulder"


class LaneDirection(models.TextChoices):
    FORWARD = "forward", "Forward"
    BACKWARD = "backward", "Backward"


class CameraType(models.TextChoices):
    FIXED = "fixed", "Fixed"
    PTZ = "ptz", "PTZ"
    DOME = "dome", "Dome"
    OTHER = "other", "Other"


class SourceType(models.TextChoices):
    # Placeholder only — Phase 3 stores NO credentials/URLs/streams (ADR-021/plan §16).
    UPLOADED = "uploaded", "Uploaded video (future)"
    RTSP = "rtsp", "RTSP (future)"
    SIMULATED = "simulated", "Simulated (future)"
    UNCONFIGURED = "unconfigured", "Unconfigured"


class CoverageType(models.TextChoices):
    PRIMARY = "primary", "Primary"
    SECONDARY = "secondary", "Secondary"
    PARTIAL = "partial", "Partial"


class ROIType(models.TextChoices):
    DETECTION = "detection", "Detection area"
    IGNORE = "ignore", "Ignore area"
    INCIDENT = "incident", "Incident zone"
    LANE_AREA = "lane_area", "Lane area"


class CountingDirection(models.TextChoices):
    AB = "a_to_b", "A→B"
    BA = "b_to_a", "B→A"
    BOTH = "both", "Both"


class LengthSource(models.TextChoices):
    MANUAL = "manual", "Manually entered"
    DERIVED = "derived", "Derived from geometry"
