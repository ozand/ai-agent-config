# Endpoint Profiles

Each endpoint has:

- a machine-readable `.yaml` profile;
- a human-readable `.md` connection guide;
- a logical credential name;
- client-specific secret-resolution instructions;
- independent verification gates.

Endpoint profiles may contain public base URLs and public model IDs. They must not contain real keys, authenticated payloads, private backend paths, live deployment secrets, or host inventories.

To add an endpoint:

1. copy `local-openai-compatible.example.yaml`;
2. assign a stable endpoint ID;
3. use an obvious placeholder or client-native secret reference;
4. add only model metadata supported by evidence;
5. add the endpoint to validation tests;
6. document credential creation without supplying a value.
