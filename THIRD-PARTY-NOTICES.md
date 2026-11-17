# 第三方声明

## three.js

本仓库 `assets/vendor/` 内含 three.js r187 的裁剪副本（`three.module.js`、`three.core.js`
及 `addons/` 下的官方示例模块），来源为 npm 包 `three@0.187.0`。

```
Copyright 2010-2026 Three.js Authors
SPDX-License-Identifier: MIT
```

MIT 许可证全文：

```
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
```

## 版本一致性

- `assets/vendor/manifest.json` 记录 `three_version: 0.187.0` 与 18 个文件的 `sha256_12`。
- `tests/test_contract.py::test_vendor_清单与文件一致` 会逐个重算哈希，任何改动都会让测试变红。
- 升级 three.js 时：重跑 `scripts/vendor.py` 生成新 vendor → 更新 `manifest.json` → 重跑全量测试。
