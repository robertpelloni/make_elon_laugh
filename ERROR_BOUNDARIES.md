# Asynchronous Error Boundaries Report

## Objective
This report flags behavioral shifts and boundaries related to error handling following the refactor of `bot.py` and `rate_limiter.py` to an asynchronous architecture using `asyncio` and `tweepy.asynchronous.AsyncClient`.

## Async Discrepancies & Boundaries

1.  **Event Loop Blocking**:
    *   **Behavior**: Previously, the synchronous `time.sleep()` blocked the entire Python thread. In the async architecture, we use `await asyncio.sleep()`.
    *   **Boundary**: If we introduce concurrent tasks (e.g., polling multiple users or answering DMs simultaneously), the current error handling allows those tasks to continue running while the rate-limited task yields control via `await asyncio.sleep()`.
2.  **Rate Limiter Wrapper**:
    *   **Behavior**: `async_call_api_with_backoff` now requires `await` when calling the provided `api_func()`.
    *   **Boundary**: If a non-awaitable synchronous function is accidentally passed as a lambda (e.g., a standard `tweepy.Client` function instead of `AsyncClient`), it will result in a `TypeError: object NoneType can't be used in 'await' expression`.
3.  **Exception Propagation**:
    *   **Behavior**: Exceptions raised inside the `asyncio.run(main())` loop are caught by the broad `except Exception as e:` block.
    *   **Boundary**: In an asynchronous context, certain fatal signals (like `asyncio.CancelledError`) need special consideration. Currently, `Exception` does *not* catch `BaseException` (like `KeyboardInterrupt` or `CancelledError`), which is correct and allows the bot to be gracefully shut down via Ctrl+C or Docker `SIGTERM`.

## Conclusion
The error-handling branch behaves as expected in the asynchronous context, successfully mimicking the synchronous exponential backoff and jitter without blocking the asyncio event loop. No critical discrepancies or regressions were identified.