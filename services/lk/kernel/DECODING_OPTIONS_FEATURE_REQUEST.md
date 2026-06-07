# Decoding Options Feature Request

The desktop popup UI now exposes advanced sampling controls, but the current kernel path only forwards:

- `max_tokens`
- `temperature`
- `timeout`

Requested kernel support:

- `top_p`
- `min_p`
- `typical_p`
- `top_k`
- `repeat_penalty`
- `presence_penalty`
- `frequency_penalty`
- `seed`
- `stop_sequences`

Suggested implementation points:

- Extend `TurnConfig` in `services/lk/kernel/invoke.py`.
- Forward supported fields through `services/lk/model.py::call_model`.
- Add CLI `/set` handling only for options the active backend actually supports.
- Keep unsupported backend options ignored with a visible warning rather than failing a turn.

The UI should treat these as desired runtime controls until the kernel bridge advertises exact support.
