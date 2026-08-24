"use client";

import { ResourceManager } from "@/components/ResourceManager";

export default function RoadsPage() {
  return (
    <ResourceManager
      title="Roads"
      path="roads"
      columns={[
        { key: "code", label: "Code" },
        { key: "name", label: "Name" },
        { key: "road_type", label: "Type" },
        { key: "directionality", label: "Directionality" },
      ]}
      fields={[
        { name: "city", label: "City", optionsFrom: "cities", required: true },
        { name: "name", label: "Name", required: true },
        { name: "code", label: "Code", required: true },
        {
          name: "road_type", label: "Type", type: "select",
          options: ["motorway", "trunk", "primary", "secondary", "tertiary", "residential", "service", "other"].map((v) => ({ value: v, label: v })),
        },
        {
          name: "directionality", label: "Directionality", type: "select",
          options: [{ value: "one_way", label: "one-way" }, { value: "two_way", label: "two-way" }],
        },
      ]}
    />
  );
}
