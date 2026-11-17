## 这个 PR 改了什么

<!-- 一句话说动机，不是「改了哪些文件」 -->

## 为什么原来的做法不对

<!-- 如果这是修复类 PR，这段必须有。没有复现的修复，等于没修。 -->

## 检查

- [ ] `python3 -m pytest tests/ -q` 全绿
- [ ] 若改了产物相关逻辑，`validate_scene.py --strict` 全绿
- [ ] 新增的数字已同步到 README / README_EN
- [ ] 若修了 bug，附了回归测试
- [ ] 没有提交 `__pycache__` / `.pytest_cache` / 临时 HTML

## 附注

<!-- 截图、取舍说明、已知遗留问题 -->
