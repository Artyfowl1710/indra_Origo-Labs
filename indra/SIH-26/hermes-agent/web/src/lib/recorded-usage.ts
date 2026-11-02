type Usage={input_tokens:number;output_tokens:number;cache_read_tokens?:number;cache_write_tokens?:number};
export const recordedInput=(usage:Usage)=>usage.input_tokens+(usage.cache_read_tokens??0)+(usage.cache_write_tokens??0);
export const recordedTotal=(usage:Usage)=>recordedInput(usage)+usage.output_tokens;
