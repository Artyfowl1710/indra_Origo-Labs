export interface ModelModalities {
  display_name?: string;
  input_modalities?: string[];
  output_modalities?: string[];
  modality_known?: boolean;
  model_kind?: string;
  chat_compatible?: boolean | null;
  vision?: boolean;
  video?: boolean;
  audio?: boolean;
  tools?: boolean | null;
}

export function modalityLabels(info?: ModelModalities): string[] {
  if (!info) return ["Capabilities unknown"];
  const inputs = info.input_modalities ?? [];
  const labels = inputs.filter(m => m !== "text").map(m => m[0].toUpperCase() + m.slice(1));
  if (info.chat_compatible === false) labels.unshift(info.model_kind ?? "Specialist");
  else if (inputs.length === 1 && inputs[0] === "text") labels.unshift("Text only");
  else if (inputs.length > 1) labels.unshift("Multimodal");
  else labels.unshift("Capabilities unknown");
  if (info.tools === false) labels.push("No tools");
  return labels;
}
