import {describe,it,expect} from "vitest";
import {recordedInput,recordedTotal} from "./recorded-usage";
describe("canonical recorded token buckets",()=>{
 it("includes cached input while leaving reasoning inside output",()=>{
  const usage={input_tokens:100,output_tokens:20,cache_read_tokens:300,cache_write_tokens:40,reasoning_tokens:10};
  expect(recordedInput(usage)).toBe(440);expect(recordedTotal(usage)).toBe(460);
 });
 it("accepts older backend rows without cache-write fields",()=>{
  expect(recordedTotal({input_tokens:100,output_tokens:20})).toBe(120);
 });
});
