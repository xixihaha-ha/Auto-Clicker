# Auto-Clicker

一个基于 `Python + tkinter + pyautogui` 的桌面自动点击工具，支持：
- 悬浮按钮（可拖拽）
- 按顺序循环点击
- 布局保存/加载（`layouts/*.json`）
- 鼠标点击录制与回放（`records/*.json`）
- 全局热键（依赖 `pynput`）

## 运行环境
- Windows 10/11（推荐）
- Python 3.9+

## 快速开始（cmd.exe）
在项目根目录执行：

```cmd
cd /d "你的项目路径\Auto-Clicker"
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt
python multi_floater_autoclicker.py
```

如果你的系统有 `py` 启动器，也可以用：

```cmd
py -3 -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt
py multi_floater_autoclicker.py
```

## 基本操作
- `↑`：开始自动点击
- `↓`：停止（自动点击/录制回放/录制）
- `←`：在鼠标当前位置新增一个悬浮按钮
- `→`：退出程序

界面按钮说明：
- **添加按钮**：在当前鼠标位置创建按钮
- **删除按钮**：删除列表中选中的按钮
- **保存布局 / 加载布局**：管理 `layouts` 目录下的布局文件
- **开始录制 / 停止录制 / 回放录制**：录制鼠标点击并按时间回放

## 文件结构说明
- `multi_floater_autoclicker.py`：主程序
- `requirements.txt`：依赖列表
- `layouts/`：布局文件目录
- `records/`：录制文件目录

程序会自动在项目目录下创建 `layouts` 和 `records` 文件夹（若不存在）。

## 常见问题
- **按热键没反应**：请确认程序在运行，且系统未拦截键盘钩子；如未安装 `pynput`，会自动降级为窗口焦点热键。
- **点击位置偏移**：与系统 DPI 缩放相关，建议显示缩放使用 100% 或在同一缩放环境下录制/使用布局。
- **杀软提示风险**：自动化点击工具可能被安全软件标记，请仅在合法、合规场景使用。

## 分享给他人的建议
把以下内容一起打包给对方：
- `multi_floater_autoclicker.py`
- `requirements.txt`
- `README.md`
- （可选）你的 `layouts/` 与 `records/` 数据文件

对方按 README 的“快速开始”步骤即可运行。
