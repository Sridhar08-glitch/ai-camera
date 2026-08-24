"use client";

import { ResourceManager } from "@/components/ResourceManager";

export default function ZonesPage() {
  return (
    <ResourceManager
      title="Zones"
      path="zones"
      columns={[
        { key: "code", label: "Code" },
        { key: "name", label: "Name" },
        { key: "city", label: "City" },
      ]}
      fields={[
        { name: "city", label: "City", optionsFrom: "cities", optionLabel: "code", required: true },
        { name: "name", label: "Name", required: true },
        { name: "code", label: "Code", required: true },
      ]}
    />
  );
}
