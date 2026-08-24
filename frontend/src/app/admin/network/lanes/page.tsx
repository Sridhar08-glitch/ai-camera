"use client";

import { ResourceManager } from "@/components/ResourceManager";

export default function LanesPage() {
  return (
    <ResourceManager
      title="Lanes"
      path="lanes"
      columns={[
        { key: "lane_index", label: "Index" },
        { key: "direction", label: "Direction" },
        { key: "lane_type", label: "Type" },
        { key: "revision", label: "Rev" },
      ]}
      fields={[
        { name: "road_segment", label: "Road segment", optionsFrom: "road-segments", optionLabel: "id", required: true },
        { name: "approach", label: "Approach", optionsFrom: "approaches", optionLabel: "id" },
        { name: "lane_index", label: "Index", type: "number", required: true },
        {
          name: "direction", label: "Direction", type: "select",
          options: [{ value: "forward", label: "forward" }, { value: "backward", label: "backward" }],
        },
        {
          name: "lane_type", label: "Type", type: "select",
          options: ["general", "bus", "bicycle", "emergency", "turn", "parking", "shoulder"].map((v) => ({ value: v, label: v })),
        },
        { name: "width_m", label: "Width (m)", type: "number" },
      ]}
    />
  );
}
