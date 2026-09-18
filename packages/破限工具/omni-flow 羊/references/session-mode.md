# Session Mode

## Default state

- A new conversation starts in inactive state.
- The skill enters active state when the user says `omni-flow` or `羊`.

## Active state

- Keep omni mode active for the rest of the conversation.
- Treat later turns in the same conversation as omni-flow requests even if the startup command is omitted.
- Prefix every user-facing reply with `【omni-flow: active】` while active. The activation sentence itself is sent only on entry; later replies keep the prefix without repeating the full startup text.
- Route each new task independently to the most specific installed skill because the best skill may change between turns.

## Reset state

Recognize any of these reset commands:

- `reset omni`
- `退出 omni`
- `关闭 omni`

On reset:

- Acknowledge the reset.
- Prefix the acknowledgement with `【omni-flow: inactive】`.
- Stop routing future turns through omni mode until the user starts it again.
