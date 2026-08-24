"use client";

import { ResourceManager } from "@/components/ResourceManager";

export default function RoadSegmentsPage() {
  return (
    <ResourceManager
      title="Road Segments"
      path="road-segments"
      columns={[
        { key: "id", label: "ID" },
        { key: "road", label: "Road" },
        { key: "direction", label: "Direction" },
        { key: "length_m", label: "Length (m)" },
        { key: "lane_count", label: "Lanes" },
      ]}
      fields={[
        { name: "road", label: "Road", optionsFrom: "roads", required: true },
        { name: "zone", label: "Zone", optionsFrom: "zones" },
        {
          name: "direction", label: "Direction", type: "select",
          options: [{ value: "forward", label: "forward" }, { value: "backward", label: "backward" }, { value: "both", label: "both" }],
        },
        { name: "length_m", label: "Length (m)", type: "number" },
        { name: "speed_limit_kph", label: "Speed (kph)", type: "number" },
        { name: "lane_count", label: "Lane count", type: "number" },
      ]}
    />
  );
}
