import { createContext, useContext } from "react";

export type FormCtx = {
  demo: boolean;
  resourceName?: string;
  identity?: string;
  mode?: "create" | "edit" | "view" | null;
};

const FormContext = createContext<FormCtx>({ demo: false });

export function FormProvider({
  demo,
  resourceName,
  identity,
  mode,
  children,
}: {
  demo: boolean;
  resourceName?: string;
  identity?: string;
  mode?: "create" | "edit" | "view" | null;
  children: React.ReactNode;
}) {
  return (
    <FormContext.Provider value={{ demo, resourceName, identity, mode }}>
      {children}
    </FormContext.Provider>
  );
}

export function useFormContext(): FormCtx {
  return useContext(FormContext);
}
