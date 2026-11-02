export const DEFAULT_REPLY_PREFIX = '✦ *Indra · Origo Labs*\n────────────\n';

// Recognize replies already on the phone before the branding upgrade as well.
const PREVIOUS_REPLY_PREFIX = '⚕ *Hermes Agent*\n────────────\n';
export function isAgentReply(body, prefix = DEFAULT_REPLY_PREFIX) {
  return typeof body === 'string' && (
    Boolean(prefix && body.startsWith(prefix)) || body.startsWith(PREVIOUS_REPLY_PREFIX)
  );
}
