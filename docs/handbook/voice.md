# Voice, profiles and appearance


Voice mode provides microphone controls, device voice selection and a provider/model selection path. Select the available input/output devices, grant microphone permission and check the chosen speech backend before starting. Device text-to-speech, transcription and a live speech model are different capabilities.

A provider's model list or a quota screenshot does not establish unlimited voice access. Account permissions, rate limits, region, connectivity and the configured API determine availability. Future providers need a compatible adapter; an arbitrary text model cannot automatically provide real-time audio.

Mute, speak and exit controls apply to the current voice session. If transcription is empty, check Windows microphone privacy settings, device selection, the configured speech provider and logs. If text is generated but silent, check output device and speech synthesis selection. Do not promise offline operation when speech uses a hosted service.

Appearance offers light, teal and ember options with other available themes. Motion should respect reduced-motion preferences. Profiles keep separate settings; verify the active profile before changing keys, model roles or connectors. Profile/user memory is local state and must be reviewed before export. Do not infer that optional cross-device memory synchronization is enabled merely because a profile exists.
