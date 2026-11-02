import type {UsageCoverageInfo} from "@/lib/api";
type Totals={total_cache_read:number;total_cache_write?:number;total_reasoning:number;total_estimated_cost:number;total_actual_cost:number;unknown_estimated_cost_rows?:number;unknown_actual_cost_rows?:number};
type Task={task:string;input_tokens:number;output_tokens:number;total_tokens?:number;api_calls:number};
export function UsageCoverage({coverage,totals,tasks=[]}:{coverage?:UsageCoverageInfo;totals:Totals;tasks?:Task[]}){
 const estimated=totals.unknown_estimated_cost_rows?totals.total_estimated_cost>0?`Partial estimate: $${totals.total_estimated_cost.toFixed(4)} + unpriced usage`:"Cost estimate unavailable":`Estimated cost: $${totals.total_estimated_cost.toFixed(4)}`;
 const actual=totals.unknown_actual_cost_rows||!totals.total_actual_cost?"No complete billed amount reported":`Reported billed subtotal: $${totals.total_actual_cost.toFixed(4)}`;
 return <section className="indra-usage-coverage" aria-label="Usage coverage"><h2>Recorded usage, with coverage.</h2><p>Includes recorded main and auxiliary work. A model switch keeps usage with the model that performed it. These figures are not a provider invoice.</p>
 <div className="indra-usage-metrics"><span>Cache reads <strong>{totals.total_cache_read.toLocaleString()}</strong></span><span>Cache writes <strong>{(totals.total_cache_write??0).toLocaleString()}</strong></span><span>Reasoning <strong>{totals.total_reasoning.toLocaleString()}</strong></span></div>
 <p>{estimated} · {actual}</p>
 <p>{coverage?.cache_basis??"Older backend: coverage details unavailable."}</p>
 <details><summary>What these numbers cover</summary><p>{coverage?.basis}</p><p>{coverage?.daily_basis}</p><p>{coverage?.missing}</p>{!!coverage?.main_residual_sessions&&<p>{coverage.main_residual_sessions} session(s) include usage available only in the session summary; model attribution for that portion may be incomplete.</p>}{!!coverage?.summary_below_detail_sessions&&<p>{coverage.summary_below_detail_sessions} session summary(s) lag recorded model details. This view retains those details.</p>}</details>
 {!!tasks.length&&<details open><summary>Work by task</summary><div className="indra-usage-task-table"><table><thead><tr><th>Task</th><th>Recorded calls</th><th>Tokens including cache</th></tr></thead><tbody>{tasks.map(task=><tr key={task.task}><td>{task.task.replaceAll("_"," ")}</td><td>{task.api_calls.toLocaleString()}</td><td>{(task.total_tokens??task.input_tokens+task.output_tokens).toLocaleString()}</td></tr>)}</tbody></table></div></details>}
 </section>;
}
