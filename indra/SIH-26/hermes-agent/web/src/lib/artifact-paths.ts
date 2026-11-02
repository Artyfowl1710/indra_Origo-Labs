const EXT="(?:md|markdown|pdf|pptx|ppt|xlsx|xls|docx|doc|csv|json|txt|png|jpg|jpeg|svg|webp)";
export function extractArtifactPaths(text:string):string[]{
 const result=new Set<string>();
 const add=(raw:string)=>{const value=raw.trim().replace(/^<|>$/g,"");if(/^https?:|^data:|^#/.test(value))return;
  if(!new RegExp(`\\.${EXT}$`,"i").test(value))return;
  const output=/(?:^|[/\\])outputs[/\\]/i.test(value);
  const deliverable=/\.(?:pdf|pptx?|xlsx?|docx?|csv)$/i.test(value);
  if(output||deliverable)result.add(value);
 };
 const links=[...text.matchAll(/\[[^\]\n]+\]\(([^)\n]+)\)/g)];
 for(const match of links)add(match[1]);
 const urls=[...text.matchAll(/https?:\/\/[^\s)]+/g)].map(m=>[m.index!,m.index!+m[0].length]);
 urls.push(...links.map(m=>[m.index!,m.index!+m[0].length]));
 const pattern=new RegExp(`(?:[A-Za-z]:[\\\\/]|\\.?\\.?[\\\\/]|/)?(?:[A-Za-z0-9_.~-]+[\\\\/])*[A-Za-z0-9_.-]+\\.${EXT}\\b`,"gi");
 for(const match of text.matchAll(pattern)){if(!urls.some(([a,b])=>match.index!>=a&&match.index!<b))add(match[0]);}
 return [...result];
}
export function artifactDisplayText(text:string):string{
 const paths=extractArtifactPaths(text);
 return text.split("```").map((part,index)=>index%2?part:paths.reduce((value,path)=>{
  const name=path.split(/[/\\]/).pop()||path;
  value=value.replace(/\[([^\]]+)\]\(([^)]+)\)/g,(whole,label,target)=>target.trim().replace(/^<|>$/g,"")===path?label:whole);
  return value.split(path).join(name);
 },part)).join("```");
}
