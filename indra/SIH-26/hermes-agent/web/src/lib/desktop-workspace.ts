declare global {interface Window {indraDesktop?:{pickFolder:()=>Promise<string|null>}}}
export const canPickFolder=()=>typeof window.indraDesktop?.pickFolder==='function';
export const pickProjectFolder=()=>window.indraDesktop?.pickFolder()??Promise.reject(new Error('Folder selection is available in the Indra desktop app.'));
