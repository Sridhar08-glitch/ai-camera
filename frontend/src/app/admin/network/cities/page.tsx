"use client";

import { ResourceManager } from "@/components/ResourceManager";

export default function CitiesPage() {
  return (
    <ResourceManager
      title="Cities"
      path="cities"
      columns={[
        { key: "code", label: "Code" },
        { key: "name", label: "Name" },
        { key: "country_code", label: "Country" },
        { key: "timezone", label: "Timezone" },
      ]}
      fields={[
        { name: "name", label: "Name", required: true },
        { name: "code", label: "Code", required: true },
        { name: "country_code", label: "Country" },
        { name: "timezone", label: "Timezone" },
        { name: "center_lat", label: "Center lat", type: "number" },
        { name: "center_lng", label: "Center lng", type: "number" },
      ]}
    />
  );
}
