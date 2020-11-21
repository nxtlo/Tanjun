# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2020, Faster Speeding
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from __future__ import annotations

__all__: typing.Sequence[str] = ["Client"]

import asyncio
import itertools
import typing

from hikari import traits as hikari_traits
from hikari.events import lifetime_events
from hikari.events import message_events

from tanjun import context
from tanjun import traits
from tanjun import utilities

if typing.TYPE_CHECKING:
    import types

ClientCheckT = typing.Callable[
    [message_events.MessageCreateEvent], typing.Union[typing.Coroutine[typing.Any, typing.Any, bool], bool]
]


class Client(traits.Client):  # TODO: prefix mention
    __slots__: typing.Sequence[str] = (
        "_cache",
        "_checks",
        "_components",
        "_dispatch",
        "hooks",
        "_prefixes",
        "_rest",
        "_shards",
    )

    def __init__(
        self,
        dispatch: hikari_traits.DispatcherAware,
        rest: typing.Optional[hikari_traits.RESTAware] = None,
        shard: typing.Optional[hikari_traits.ShardAware] = None,
        cache: typing.Optional[hikari_traits.CacheAware] = None,
        /,
        *,
        hooks: typing.Optional[traits.Hooks] = None,
        prefixes: typing.Optional[typing.Iterable[str]] = None,
    ) -> None:
        if rest is None and isinstance(cache, hikari_traits.RESTAware):
            rest = cache

        elif rest is None and isinstance(dispatch, hikari_traits.RESTAware):
            rest = dispatch

        elif rest is None and isinstance(shard, hikari_traits.RESTAware):
            rest = shard  # type: ignore[unreachable]

        else:
            raise ValueError("Missing RESTAware client implementation.")

        if shard is None and isinstance(dispatch, hikari_traits.ShardAware):
            shard = dispatch

        elif shard is None and isinstance(cache, hikari_traits.ShardAware):
            shard = cache

        elif shard is None and isinstance(rest, hikari_traits.ShardAware):
            shard = rest

        else:
            raise ValueError("Missing ShardAware client implementation.")

        # Unlike `rest`, no provided Cache implementation just means this runs stateless.
        if cache is None and isinstance(dispatch, hikari_traits.CacheAware):
            cache = dispatch

        elif cache is None and isinstance(rest, hikari_traits.CacheAware):
            cache = rest

        elif cache is None and isinstance(shard, hikari_traits.CacheAware):  # type: ignore[unreachable]
            cache = shard  # type: ignore[unreachable]
        # TODO: logging or something to indicate this is running statelessly rather than statefully.

        self.hooks = hooks
        self._checks: typing.MutableSet[ClientCheckT] = {
            self.check_human,
        }
        self._cache = cache
        self._components: typing.MutableSet[traits.Component] = set()
        self._dispatch = dispatch
        self._prefixes = set(prefixes) if prefixes else set()
        self._rest = rest
        self._shards = shard
        self._dispatch.dispatcher.subscribe(lifetime_events.StartingEvent, self._on_starting_event)
        self._dispatch.dispatcher.subscribe(lifetime_events.StoppingEvent, self._on_stopping_event)

    async def __aenter__(self) -> Client:
        await self.open()
        return self

    async def __aexit__(
        self,
        exception_type: typing.Optional[typing.Type[BaseException]],
        exception: typing.Optional[BaseException],
        exception_traceback: typing.Optional[types.TracebackType],
    ) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"CommandClient <{type(self).__name__!r}, {len(self._components)}" f" components, {self._prefixes}>"

    @property
    def cache(self) -> typing.Optional[hikari_traits.CacheAware]:
        return self._cache

    @property
    def components(self) -> typing.AbstractSet[traits.Component]:
        return frozenset(self._components)

    @property
    def dispatch(self) -> hikari_traits.DispatcherAware:
        return self._dispatch

    @property
    def prefixes(self) -> typing.AbstractSet[str]:
        return frozenset(self._prefixes)

    @property
    def rest(self) -> hikari_traits.RESTAware:
        return self._rest

    @property
    def shards(self) -> hikari_traits.ShardAware:
        return self._shards

    async def _on_starting_event(self, _: lifetime_events.StartingEvent, /) -> None:
        await self.open()

    async def _on_stopping_event(self, _: lifetime_events.StoppingEvent, /) -> None:
        await self.close()

    def add_check(self, check: ClientCheckT, /) -> None:
        self._checks.add(check)

    def remove_check(self, check: ClientCheckT, /) -> None:
        self._checks.remove(check)

    async def check(self, event: message_events.MessageCreateEvent, /) -> bool:
        return await utilities.gather_checks(utilities.await_if_async(check(event)) for check in self._checks)

    def add_component(self, component: traits.Component, /) -> None:
        component.bind_client(self)
        self._components.add(component)

    def remove_component(self, component: traits.Component, /) -> None:
        self._components.remove(component)

    def add_prefix(self, prefix: str, /) -> None:
        self._prefixes.add(prefix)

    def remove_prefix(self, prefix: str, /) -> None:
        self._prefixes.remove(prefix)

    async def check_context(self, ctx: traits.Context, /) -> typing.AsyncIterator[traits.FoundCommand]:
        async for value in utilities.async_chain(component.check_context(ctx) for component in self._components):
            yield value

    @staticmethod
    def check_human(event: message_events.MessageCreateEvent) -> bool:
        return event.is_human

    def check_name(self, name: str, /) -> typing.Iterator[traits.FoundCommand]:
        yield from itertools.chain.from_iterable(component.check_name(name) for component in self._components)

    async def check_prefix(self, content: str, /) -> typing.Optional[str]:
        for prefix in self._prefixes:
            if content.startswith(prefix):
                return prefix

        return None

    async def close(self, *, deregister_listener: bool = True) -> None:
        self._dispatch.dispatcher.unsubscribe(message_events.MessageCreateEvent, self.on_message_create)

        if deregister_listener:
            await asyncio.gather(*(component.close() for component in self._components))

    async def open(self, *, register_listener: bool = True) -> None:
        await asyncio.gather(*(component.open() for component in self._components))

        if register_listener:
            self._dispatch.dispatcher.subscribe(message_events.MessageCreateEvent, self.on_message_create)

    async def on_message_create(self, event: message_events.MessageCreateEvent) -> None:
        if event.message.content is None:
            return

        if (prefix := await self.check_prefix(event.message.content)) is None or not await self.check(event):
            return

        content = event.message.content[len(prefix) :]
        ctx = context.Context(self, content=content, message=event.message, triggering_prefix=prefix)

        hooks = {self.hooks,} if self.hooks else set()

        for component in self._components:
            if await component.execute(ctx, hooks=hooks):
                break
