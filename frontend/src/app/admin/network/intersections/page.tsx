"use client";

import { ResourceManager } from "@/components/ResourceManager";

export default function IntersectionsPage() {
  return (
    <ResourceManager
      title="Intersections"
      path="intersections"
      columns={[
        { key: "code", label: "Code" },
        { key: "name", label: "Name" },
        { key: "intersection_type", label: "Type" },
      ]}
      fields={[
        { name: "city", label: "City", optionsFrom: "cities", required: true },
        { name: "zone", label: "Zone", optionsFrom: "zones" },
        { name: "name", label: "Name", required: true },
        { name: "code", label: "Code", required: true },
        {
          name: "intersection_type", label: "Type", type: "select",
          options: ["signalized", "unsignalized", "roundabout", "junction", "other"].map((v) => ({ value: v, label: v })),
        },
        { name: "location_lat", label: "Lat", type: "number" },
        { name: "location_lng", label: "Lng", type: "number" },
      ]}
    />
  );
}
