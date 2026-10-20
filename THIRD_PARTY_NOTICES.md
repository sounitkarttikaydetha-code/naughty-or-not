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

## ReportLab PDF Generation Library

ReportLab is licensed under the BSD License:
Copyright (c) 2000-2024, ReportLab Inc.
All rights reserved.

### Licensing Note & DarkGarden GPL Font Exclusion
ReportLab distribution packages bundle an optional font `DarkGarden` (`DarkGarden-Regular.afm`) licensed under the GNU General Public License v2 (GPLv2). Sanction checK uses standard PostScript/PDF core fonts (Helvetica) exclusively and explicitly excludes all DarkGarden files in `build.spec` and runtime font registries, ensuring no copyleft font assets are distributed in binary packages.

