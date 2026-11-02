import { expect,it } from "vitest";
import {extractArtifactPaths,artifactDisplayText} from "./artifact-paths";
it("recognizes Windows and markdown paths without treating web links as local artifacts",()=>{
 expect(extractArtifactPaths("Created C:\\work\\outputs\\deck.pptx and [report](C:/My Project/outputs/report.pdf). https://example.com/source.pdf")).toEqual(["C:/My Project/outputs/report.pdf","C:\\work\\outputs\\deck.pptx"]);
});
it("keeps source code examples while shortening artifact paths in prose",()=>{
 const source="Here is outputs/report.pdf\n```\nopen('outputs/report.pdf')\n```";
 expect(artifactDisplayText(source)).toBe("Here is report.pdf\n```\nopen('outputs/report.pdf')\n```");
});
it("does not turn ordinary source filenames into deliverables",()=>{
 expect(extractArtifactPaths("Read README.md and package.json before editing.")).toEqual([]);
});
