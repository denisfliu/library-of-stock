# Third-party notices

This repo's own code is MIT (see `LICENSE`). It also ships vendored
third-party code, loads some libraries from CDNs, and builds on external
content and models. This file collects the required notices and provenance.

## Vendored code (redistributed in this repo)

### qb-answer-checker 1.1.9 — ISC © Geoffrey Wu

`lib/js/answer_checker.js` is a verbatim vendoring of
[qb-answer-checker](https://github.com/qbreader/qb-answer-checker)
(qbreader's answer-judging library, commit c6a7f49) with its four runtime
dependencies inlined; see the file header for the exact packaging notes.
Upstream declares the ISC license in its package metadata; the standard ISC
text with the package author's copyright follows:

> Copyright (c) Geoffrey Wu
>
> Permission to use, copy, modify, and/or distribute this software for any
> purpose with or without fee is hereby granted, provided that the above
> copyright notice and this permission notice appear in all copies.
>
> THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
> WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
> MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
> ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
> WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
> ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
> OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

### damerau-levenshtein-js 1.1.8 — MIT © 2018 Fabvalaaah

Inlined inside `lib/js/answer_checker.js`.

> MIT License
>
> Copyright (c) 2018 Fabvalaaah - fabvalaaah@laposte.net
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

### stemmer 2.0.1 — MIT © 2014 Titus Wormer

Inlined inside `lib/js/answer_checker.js`.

> (The MIT License)
>
> Copyright (c) 2014 Titus Wormer <tituswormer@gmail.com>
>
> Permission is hereby granted, free of charge, to any person obtaining
> a copy of this software and associated documentation files (the
> 'Software'), to deal in the Software without restriction, including
> without limitation the rights to use, copy, modify, merge, publish,
> distribute, sublicense, and/or sell copies of the Software, and to
> permit persons to whom the Software is furnished to do so, subject to
> the following conditions:
>
> The above copyright notice and this permission notice shall be
> included in all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND,
> EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
> MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
> IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
> CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
> TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
> SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

### number-to-words 1.2.4 — MIT © 2015 Martin Eneqvist

Inlined inside `lib/js/answer_checker.js`.

> The MIT License (MIT)
>
> Copyright (c) 2015 Martin Eneqvist <marlun78@hotmail.com> (https://github.com/marlun78)
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

### roman-numerals 0.3.2 — MIT © 2013 Arnaud 'red' Rouyer

Inlined inside `lib/js/answer_checker.js`.

> The MIT License (MIT)
> Copyright (c) 2013 Arnaud 'red' ROUYER
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
> EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
> MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
> IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
> DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
> OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
> OR OTHER DEALINGS IN THE SOFTWARE.

## Libraries loaded from CDNs (not redistributed here)

The rendered pages load these at view time from public CDNs; each ships its
own license notices:

- [Leaflet](https://leafletjs.com/) 1.9.4 — BSD-2-Clause © Volodymyr Agafonkin
- [abcjs](https://www.abcjs.net/) 6.4.4 — MIT © Paul Rosen and Gregory Dyke
- [sql.js](https://sql.js.org/) — MIT
- [JSZip](https://stuk.github.io/jszip/) — MIT/GPLv3 dual license (used under MIT)

## Content, data, and models

- **Question content** comes from [qbreader](https://www.qbreader.org/) and
  was written by the packet authors and editors of the respective
  tournaments. The local mirror is built by the user from qbreader's
  official backups (`qbmirror import-backup`); the raw database is not
  redistributed in this repo. Rendered pages credit the source set for
  every question shown.
- **Audio soundbites and images** on study/overview pages are hot-linked
  from [Wikimedia Commons](https://commons.wikimedia.org/); each embed
  links back to its Commons file page, where the specific work's license
  and author are listed.
- **Read-aloud audio** (the `uild42/qb-audio` dataset) is synthesized with
  [Chatterbox TTS](https://github.com/resemble-ai/chatterbox) (MIT,
  Resemble AI) from qbreader question text; see the dataset card for its
  own credits.
- **Embeddings** for semantic search are produced locally with
  [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
  (Apache-2.0, Alibaba Cloud).
