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

## assets/three（离线 IIFE 运行时）

`assets/three/` 是同一份 `three@0.187.0` 的另一种打包形态，供 `scripts/build_standalone.py`
在 `file://` 下使用：

| 路径 | 内容 | 来源 |
|---|---|---|
| `three.bundle.min.js` | three r187 + 64 个可解构 addon，IIFE，挂 `globalThis.THREE_BUNDLE` | 由 `three@0.187.0` 与其官方 `examples/jsm/` 模块打包 |
| `addons/` | 77 个文件，按依赖闭包复制，与 `assets/vendor/addons/` 同源 | 同上 |
| `LICENSE` | three.js 的 MIT 全文 | 同上 |

打包产物尾部**逐字保留**了上游许可证头，未删改：

```
/**
 * @license
 * Copyright 2010-2026 Three.js Authors
 * SPDX-License-Identifier: MIT
 */
/**
 * lil-gui
 * https://lil-gui.georgealways.com
 * @version 0.17.0
 * @author George Michael Brower
 * @license MIT
 */
```

其中 `lil-gui@0.17.0` 以 MIT 许可随 `GUI` 导出一并分发。

## 产物里的 URL 不是网络请求

`build_standalone.py` 的产物会包含少量 `<scheme>://` 字面量，全部属于**标识符或署名**，
不会发起任何请求：

- `http://www.w3.org/1999/xhtml`、`http://www.w3.org/1999/xlink` —— XML 命名空间 URI，
  按规范就是字符串常量，浏览器只做命名空间比对。
- 上述许可证注释里的项目主页地址。

`tests/test_contract.py::test_D1_产物零远程引用` 对 `bundle.py` 的产物断言远程引用数为 0；
IIFE 产物按上述口径单独核对，不以「0 个 URL 字符串」为准。

## 版本一致性

- `assets/vendor/manifest.json` 记录 `three_version: 0.187.0` 与 18 个文件的 `sha256_12`。
- `tests/test_contract.py::test_vendor_清单与文件一致` 会逐个重算哈希，任何改动都会让测试变红。
- 升级 three.js 时：重跑 `scripts/vendor.py` 生成新 vendor → 更新 `manifest.json` → 重跑全量测试。
