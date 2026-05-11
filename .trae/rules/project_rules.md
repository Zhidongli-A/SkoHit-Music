# SkoHit Music 项目规则

## 代码提交规则

### 自动推送规则
- **每次修改完成后必须自动推送到 Git 仓库**
- 流程：修改文件 → `git add` → `git commit` → `git push`
- 不需要询问用户确认，直接执行推送

### 提交信息规范
- 使用英文或中文提交信息
- 格式: `<type>: <description>`
- 常用 type:
  - `feat`: 新功能
  - `fix`: 修复 bug
  - `refactor`: 重构代码
  - `chore`: 构建/工具/配置变更
  - `docs`: 文档更新

## Docker 构建规则

### pip 镜像源
- 默认使用清华大学镜像源: `https://pypi.tuna.tsinghua.edu.cn/simple`
