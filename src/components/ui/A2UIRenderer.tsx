"use client";

import pointer from "jsonpointer";
import type { SurfaceComponentBlueprint, JsonValue } from "@/lib/contracts/types";
import { trustedCatalog, type TrustedComponentName } from "@/components/ui/catalog";

type A2UIRendererProps = {
  components: SurfaceComponentBlueprint[];
  dataModel: Record<string, JsonValue>;
};

function bindProps(
  component: SurfaceComponentBlueprint,
  dataModel: Record<string, JsonValue>
): Record<string, JsonValue> {
  const boundProps: Record<string, JsonValue> = { ...(component.props ?? {}) };
  for (const binding of component.bindings ?? []) {
    boundProps[binding.prop] = pointer.get(dataModel, binding.path) as JsonValue;
  }
  return boundProps;
}

export function A2UIRenderer({ components, dataModel }: A2UIRendererProps) {
  if (!components || components.length === 0) return null;

  return (
    <div className="flex flex-col gap-6 w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
      {components.map((component) => {
        const Component = trustedCatalog[component.component as TrustedComponentName];
        
        if (!Component) {
          console.warn(`[A2UIRenderer] Component '${component.component}' not found in trusted catalog.`);
          return null;
        }
        
        const props = bindProps(component, dataModel);
        return <Component key={component.id} {...props} />;
      })}
    </div>
  );
}