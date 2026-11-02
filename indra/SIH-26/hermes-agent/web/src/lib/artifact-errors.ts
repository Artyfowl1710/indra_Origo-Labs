export function artifactOpenMessage(error:unknown):string{
  const message=error instanceof Error?error.message:String(error);
  if(/^404\b/.test(message))return "This file is unavailable. It may not have been created, or its generation failed or awaited approval.";
  if(/^409\b/.test(message))return "More than one file has this name. Select the intended file from Artifacts & Deliverables.";
  if(/^40[03]\b/.test(message))return "This file is not available in the current workspace.";
  return "The file could not be opened. Try again or check Artifacts & Deliverables.";
}
