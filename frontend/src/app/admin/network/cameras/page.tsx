"use client";

import { ResourceManager } from "@/components/ResourceManager";

export default function CamerasPage() {
  return (
    <ResourceManager
      title="Cameras"
      path="cameras"
      columns={[
        { key: "code", label: "Code" },
        { key: "name", label: "Name" },
        { key: "camera_type", label: "Type" },
        { key: "source_type", label: "Source" },
        { key: "revision", label: "Rev" },
      ]}
      fields={[
        { name: "city", label: "City", optionsFrom: "cities", required: true },
        { name: "intersection", label: "Intersection", optionsFrom: "intersections" },
        { name: "zone", label: "Zone", optionsFrom: "zones" },
        { name: "name", label: "Name", required: true },
        { name: "code", label: "Code", required: true },
        {
          name: "camera_type", label: "Type", type: "select",
          options: ["fixed", "ptz", "dome", "other"].map((v) => ({ value: v, label: v })),
        },
        { name: "location_lat", label: "Lat", type: "number" },
        { name: "location_lng", label: "Lng", type: "number" },
        { name: "bearing_deg", label: "Bearing", type: "number" },
      ]}
    />
  );
}
