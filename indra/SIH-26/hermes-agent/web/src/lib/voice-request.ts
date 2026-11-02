/** Owns one transcription request; late results must check isCurrent(). */
export class VoiceRequestGate {
  private active?: AbortController;

  begin() {
    this.cancel();
    const controller = new AbortController();
    this.active = controller;
    return {
      signal: controller.signal,
      isCurrent: () => this.active === controller && !controller.signal.aborted,
    };
  }

  cancel() {
    this.active?.abort();
    this.active = undefined;
  }
}
