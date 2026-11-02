type DeviceVoice = { name: string; localService: boolean };

/** Never let an unavailable selection silently fall back to a network voice. */
export function chooseDeviceVoice<T extends DeviceVoice>(voices: readonly T[], selected: string): T | undefined {
  const local = voices.filter((voice) => voice.localService === true);
  return local.find((voice) => voice.name === selected) ?? local[0];
}
