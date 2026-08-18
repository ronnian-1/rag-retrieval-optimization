from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict, List, Literal, Union, cast

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult


class CustomAsyncIteratorCallbackHandler(AsyncCallbackHandler):
    """Callback handler that returns an async iterator."""

    queue: asyncio.Queue[str]

    done: asyncio.Event

    @property
    def always_verbose(self) -> bool:
        return True

    def __init__(self) -> None:
        # 初始化队列和事件
        self.queue = asyncio.Queue()
        self.done = asyncio.Event()

        # 初始化答案前缀和答案到达标志
        self.answer_prefix_tokens = ["Final", "Answer", ":"]
        self.answer_reached = False
        self.last_tokens = [""] * len(self.answer_prefix_tokens)

    async def on_llm_start(
            self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        # If two calls are made in a row, this resets the state
        self.done.clear()
        self.answer_reached = False #  将answer_reached设置为False
        # print(prompts)

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:

        if token is not None and token != "":
            self.last_tokens.append(token.strip())
            if len(self.last_tokens) > len(self.answer_prefix_tokens) + 1:
                self.last_tokens.pop(0)

            if self.last_tokens[:-1] == self.answer_prefix_tokens:
                self.answer_reached = True

            if self.answer_reached:
                self.queue.put_nowait(token)

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if self.answer_reached:
            self.done.set()

    async def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self.done.set()

    async def aiter(self) -> AsyncIterator[str]:
        while not self.queue.empty() or not self.done.is_set():
            # Wait for the next token in the queue,
            # but stop waiting if the done event is set
            done, other = await asyncio.wait(
                [
                    # NOTE: If you add other tasks here, update the code below,
                    # which assumes each set has exactly one task each
                    asyncio.ensure_future(self.queue.get()),
                    asyncio.ensure_future(self.done.wait()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel the other task
            if other:
                other.pop().cancel()

            # Extract the value of the first completed task
            token_or_done = cast(Union[str, Literal[True]], done.pop().result())

            # If the extracted value is the boolean True, the done event was set
            if token_or_done is True:
                break

            # Otherwise, the extracted value is a token, which we yield
            yield token_or_done
