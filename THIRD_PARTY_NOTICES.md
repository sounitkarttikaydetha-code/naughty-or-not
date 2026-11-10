# Third-Party Notices — Clearance Check v1.2.0

This software incorporates open-source libraries, fonts, and logic derived from third-party open-source projects. All trademarks, service marks, and trade names are the property of their respective owners.

---

## 1. Moov Watchman (Search & Scoring Logic)

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
You may obtain a copy of the License at:
    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

---

## 2. Inter Typeface

Inter font is licensed under the SIL Open Font License 1.1 (OFL-1.1):
Copyright (c) 2016-2024 The Inter Project Authors (https://github.com/rsms/inter)
Embedded font asset: `assets/fonts/Inter-Regular.woff2`

Permission is hereby granted, free of charge, to any person obtaining a copy
of the Font Software, to use, study, copy, merge, embed, modify, redistribute,
and sell modified and unmodified copies of the Font Software, subject to the
conditions of the SIL Open Font License 1.1.

---

## 3. OpenSanctions Crawlers (MHA / UAPA Data Mappings)

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

---

## 4. ReportLab PDF Generation Library

ReportLab is licensed under the BSD License:
Copyright (c) 2000-2024, ReportLab Inc. All rights reserved.

### Licensing Note & DarkGarden GPL Font Exclusion
ReportLab distribution packages bundle an optional font `DarkGarden` (`DarkGarden-Regular.afm`) licensed under the GNU General Public License v2 (GPLv2). Clearance Check uses standard PostScript/PDF core fonts (Helvetica) exclusively and explicitly excludes all DarkGarden files in `build.spec` and runtime font registries, ensuring no copyleft font assets are distributed in binary packages.

---

## 5. Streamlit

Streamlit is licensed under the Apache License 2.0:
Copyright 2018-2026 Snowflake Inc.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License.

---

## 6. OpenPyXL

OpenPyXL is licensed under the MIT / Expat License:
Copyright (c) 2010 openpyxl

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction.

---

## 7. anyascii Transliteration Library

anyascii is licensed under the ISC License:
Copyright 2020-2024 anyascii

Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted.

---

## 8. Metaphone (Double Metaphone)

Metaphone is licensed under the BSD 3-Clause License:
Copyright (c) Andrew Collins. All rights reserved.

---

## 9. RapidFuzz

RapidFuzz string similarity library is licensed under the MIT License:
Copyright (c) 2020-present Max Bachmann.

---

## 10. PyYAML

PyYAML is licensed under the MIT License:
Copyright (c) 2017-2024 Ingy döt Net, Kirill Simonov.

---

## 11. Requests

Requests HTTP library is licensed under the Apache License 2.0:
Copyright 2019 Kenneth Reitz.

---

## 12. pdfplumber

pdfplumber is licensed under the MIT License:
Copyright (c) 2015 Jeremy Singer-Vine.

---

## 13. pywebview

pywebview desktop GUI wrapper is licensed under the BSD 3-Clause License:
Copyright (c) 2014-2024 Roman Sakno and contributors. All rights reserved.

---

## 14. Microsoft Edge WebView2 Runtime

Microsoft Edge WebView2 Runtime is governed by the Microsoft Software License Terms:
Copyright (c) Microsoft Corporation. All rights reserved.
The Evergreen WebView2 Runtime is installed system-wide on Windows 10 and 11, or acquired via the Microsoft Evergreen Bootstrapper under Microsoft's redistribution terms:
https://developer.microsoft.com/en-us/microsoft-edge/webview2/

---

## 15. Inno Setup

Inno Setup installer generator is licensed under the Inno Setup License:
Copyright (C) 1997-2024 Jordan Russell. All rights reserved.
Portions Copyright (C) 2000-2024 Martijn Laan. All rights reserved.

---

## 16. PyInstaller Bootloader

PyInstaller is licensed under the GNU General Public License v2 (GPLv2) with a special Bootloader Exception:
Copyright (c) 2010-2024, PyInstaller Development Team.
Binary distribution is permitted under the terms of the PyInstaller Bootloader Exception.
