import { Markdown } from "@/components/Markdown";
import { PluginSlot } from "@/plugins";
import { BRAND } from "@/config/brand";
import guide from "../../../../../../docs/WORKSPACE_UPGRADE.md?raw";
import phoneGuide from "../../../../../../docs/PHONE_CONTROL.md?raw";

/** The shipped product manual is available offline, without an external iframe. */
export default function DocsPage() {
  return <div className="min-h-0 flex-1 overflow-y-auto p-6 sm:p-10">
    <PluginSlot name="docs:top" />
    <article className="indra-guide mx-auto max-w-4xl space-y-6 rounded-2xl border border-border bg-card text-card-foreground p-6 sm:p-10">
      <header><p className="text-xs tracking-widest text-muted-foreground">{BRAND.organisation}</p>
        <h1 className="mt-2 text-3xl font-bold text-foreground">{BRAND.name} guide</h1>
        <p className="mt-2 text-sm text-muted-foreground">Installed with your workspace. Available offline.</p></header>
      <Markdown content={guide} />
      <section id="phone-control" className="scroll-mt-24 border-t border-border pt-6">
        <Markdown content={phoneGuide} />
      </section>
    </article>
    <PluginSlot name="docs:bottom" />
  </div>;
}
