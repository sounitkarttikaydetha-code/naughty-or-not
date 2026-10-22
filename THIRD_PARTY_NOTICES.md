# Third-Party Notices

This project incorporates material or logic derived from third-party open-source projects:

## OpenSanctions Crawlers (MHA / UAPA Data Mappings)

Portions of the India MHA data mapping, sub-group splitting, and crawler extraction patterns in `modules/india/` are derived from or inspired by OpenSanctions (`zavod` crawler for `in_mha_banned`), available at:
https://github.com/opensanctions/opensanctions
Source commit: `bed2bdb6a9762d18a54ef455b1b1d9839375e7c4`

### MIT License

Copyright (c) 2021-2026 OpenSanctions Community Interest Company

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## anyascii Transliteration Library

anyascii is licensed under the ISC License:
Copyright 2020-2024 anyascii

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

## ReportLab PDF Generation Library

ReportLab is licensed under the BSD License:
Copyright (c) 2000-2024, ReportLab Inc.
All rights reserved.

### Licensing Note & DarkGarden GPL Font Exclusion
ReportLab distribution packages bundle an optional font `DarkGarden` (`DarkGarden-Regular.afm`) licensed under the GNU General Public License v2 (GPLv2). Sanction checK uses standard PostScript/PDF core fonts (Helvetica) exclusively and explicitly excludes all DarkGarden files in `build.spec` and runtime font registries, ensuring no copyleft font assets are distributed in binary packages.

## Moov Watchman (Search & Scoring Logic)

Portions of the entity scoring, token combinations, Jaro-Winkler weighting, name normalization, and data loading routines in `modules/engine/` (`scoring.py`, `name_prep.py`, `loader.py`, `engine.py`) are ported from Moov Watchman (v1.2.2), available at:
https://github.com/moov-io/watchman
Source commit: `7f44b4b646638706bde187f0393b285b0fd14159`
Ported source files:
- `pkg/search/similarity_fuzzy.go`
- `pkg/search/similarity_exact.go`
- `pkg/search/similarity_close.go`
- `pkg/search/similarity.go`
- `pkg/search/algorithm.go`
- `pkg/search/models.go`

### Apache License 2.0

Copyright 2024 The Moov Authors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

## RapidFuzz

RapidFuzz string similarity library is licensed under the MIT License:
Copyright (c) 2020-present Max Bachmann

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## pywebview

pywebview desktop GUI wrapper is licensed under the BSD 3-Clause License:
Copyright (c) 2014-2024 Roman Sakno and contributors
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software without
   specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

## Microsoft Edge WebView2 Runtime

Microsoft Edge WebView2 Runtime is governed by the Microsoft Software License Terms:
Copyright (c) Microsoft Corporation. All rights reserved.
The Evergreen WebView2 Runtime is installed system-wide on Windows 10 and 11, or acquired via the Microsoft Evergreen Bootstrapper under Microsoft's redistribution terms:
https://developer.microsoft.com/en-us/microsoft-edge/webview2/

## Inno Setup

Inno Setup installer generator is licensed under the Inno Setup License:
Copyright (C) 1997-2024 Jordan Russell. All rights reserved.
Portions Copyright (C) 2000-2024 Martijn Laan. All rights reserved.

This software is provided "as-is," without any express or implied warranty. In no event shall the author be held liable for any damages arising from the use of this software.
Permission is granted to anyone to use this software for any purpose, including commercial applications, and to alter it and redistribute it freely.

## PyInstaller Bootloader

PyInstaller is licensed under the GNU General Public License v2 (GPLv2) with a special Bootloader Exception:
Copyright (c) 2010-2024, PyInstaller Development Team.

### Bootloader Exception
Under Section 7 of the GNU General Public License version 2, you are granted additional permission to distribute the binaries produced by PyInstaller (including the Bootloader) under terms of your choice, provided that you comply with the terms of the licenses of all other bundled software.

## Bundled Typefaces and Fonts

- Standard PostScript Core Fonts (Helvetica, Courier, Times): Used directly via standard PDF specification without binary font bundling.
- DejaVu Fonts: Licensed under the DejaVu Fonts License (derived from Bitstream Vera and Arev fonts, permitting free distribution and bundling).
- Noto Fonts: Licensed under the SIL Open Font License 1.1 (OFL-1.1), permitting embedding and bundling.



