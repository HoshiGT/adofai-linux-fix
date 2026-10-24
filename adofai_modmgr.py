#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADOFAI Mod Manager —— 拖拽安装式 UMM 模组管理器 (GTK4)
========================================================
把 Mod 的 zip（或含 Info.json 的文件夹）直接拖进窗口即完成安装，
并支持查看 / 启用 / 禁用 / 卸载已安装模组。零 pip 依赖（系统 PyGObject + GTK4）。

CLI 用法（不启动界面）:
    python3 adofai_modmgr.py --list
    python3 adofai_modmgr.py --install <zip 或文件夹>
    python3 adofai_modmgr.py --toggle <ModId> on|off
    python3 adofai_modmgr.py --remove <文件夹名>
    python3 adofai_modmgr.py --game "/path/to/A Dance of Fire and Ice"
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from adofai_fix import (C_BOLD, C_CYAN, C_GREEN, C_RED, C_RESET, C_YELLOW,
                        build_type_label, detect_build_type, find_adofai_dir,
                        find_all_adofai_dirs, get_managed_dir)

GAME_PROCESS_HINT = "ADanceOfFireAndIce"
CONFIG_FILE = Path.home() / ".config" / "adofai_modmgr.json"

SUPPORTED_LANGS = ("zh", "en", "ko")


def load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(cfg: dict):
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False),
                               encoding="utf-8")
    except Exception:
        pass


def load_saved_game_dir() -> Optional[str]:
    """读取 GUI 上次选择的游戏目录（用户自选目录优先于自动探测）。"""
    return load_config().get("game_dir")


def save_game_dir(path: Path):
    cfg = load_config()
    cfg["game_dir"] = str(path)
    save_config(cfg)


# ---------------------------------------------------------------- i18n
# 以中文原文为 key 的轻量字典翻译（零依赖，不引入 gettext）。

STRINGS: Dict[str, Dict[str, str]] = {
    "zh": {},
    "en": {
        # 核心 ModManager 消息
        "路径不存在": "Path does not exist",
        "仅支持 .zip 压缩包或包含 Info.json 的文件夹":
            "Only .zip archives or folders containing Info.json are supported",
        "zip 内未找到 Info.json（这看起来不是 UMM 模组包）":
            "Info.json not found in zip (this does not look like a UMM mod package)",
        "Info.json 解析失败: {ex}": "Failed to parse Info.json: {ex}",
        "Info.json 缺少合法的 Id 字段": "Info.json has no valid Id field",
        "不是有效的 zip 文件": "Not a valid zip file",
        "Info.json 所在层级为空": "The level containing Info.json is empty",
        "检测到路径穿越条目，已中止: {n}": "Path traversal entry detected, aborted: {n}",
        "已安装 {name} v{ver}{note}": "Installed {name} v{ver}{note}",
        "安装失败: {ex}": "Install failed: {ex}",
        "Params.xml 尚未生成，请先启动一次游戏再操作开关":
            "Params.xml has not been generated yet — launch the game once before toggling",
        "写入 Params.xml 失败: {ex}": "Failed to write Params.xml: {ex}",
        "已启用": "Enabled",
        "已禁用": "Disabled",
        "{state} {mod_id}{note}": "{state} {mod_id}{note}",
        "（注意：游戏正在运行，退出游戏时可能被覆盖）":
            " (note: game is running; changes may be overwritten when the game exits)",
        "（注意：游戏正在运行，重新启动游戏后生效）":
            " (note: game is running; takes effect after restarting the game)",
        "模组目录不存在: {folder}": "Mod directory does not exist: {folder}",
        "已卸载 {folder}{note}": "Uninstalled {folder}{note}",
        "已注入 {entry_assembly}（入口 {entry_point}）{note}":
            "Injected into {entry_assembly} (entry point {entry_point}){note}",
        "已移除 UMM 注入补丁（UMM 文件保留）":
            "UMM injection patch removed (UMM files kept)",
        "已用 .original_ 备份恢复原始程序集（UMM 与模组将不再加载）":
            "Restored original assembly from .original_ backup (UMM and mods will no longer load)",
        "zip 内未找到 UnityModManager.dll（这是 UMM 发行包吗？）":
            "UnityModManager.dll not found in zip (is this a UMM release package?)",
        "已安装 UMM 运行时（{count} 个文件）→ Managed/UnityModManager/":
            "UMM runtime installed ({count} files) → Managed/UnityModManager/",
        "未找到 dist/UMMInjector.exe 且自动编译失败 (需要 mono 与游戏内 dnlib.dll)":
            "dist/UMMInjector.exe not found and automatic build failed (needs mono and the game's dnlib.dll)",
        "运行注入器失败: {ex}": "Failed to run injector: {ex}",
        "注入器无输出": "Injector produced no output",
        "Linux 原生版": "Linux native",
        "Windows 版 (Proton/Wine)": "Windows build (Proton/Wine)",
        "Linux + Windows 双版本": "Linux + Windows dual build",
        # CLI
        "[-] 未能识别 ADOFAI 游戏目录，请用 --game 指定或设置 ADOFAI_PATH。":
            "[-] Could not locate the ADOFAI game directory — use --game or set ADOFAI_PATH.",
        "全局搜索到以下候选目录:": "Global search found the following candidate directories:",
        "请用 --game 指定其一，或直接运行 GUI 选择。":
            "Pass one with --game, or pick one in the GUI.",
        "游戏: {dir}  (UMM 注入: {inj})": "Game: {dir}  (UMM injected: {inj})",
        "是": "yes", "否": "no",
        "共 {n} 个模组": "{n} mods total",
        "未安装 PyGObject，无法启动图形界面。":
            "PyGObject not installed — cannot start the GUI.",
        "Ubuntu/Debian: sudo apt install python3-gi gir1.2-gtk-4.0":
            "Ubuntu/Debian: sudo apt install python3-gi gir1.2-gtk-4.0",
        # GUI
        "Unity Mod Manager — ADOFAI 模组管理器":
            "Unity Mod Manager — ADOFAI Mod Manager",
        "启动游戏": "Launch game", "打开 Mods 目录": "Open Mods folder",
        "模组": "Mods", "日志": "Log", "安装器": "Installer",
        "启用": "Enabled", "名称": "Name", "版本": "Version",
        "作者": "Author", "文件夹": "Folder",
        "安装模组…": "Install Mod…", "打开文件夹": "Open Folder",
        "卸载": "Uninstall",
        "或将 Mod 的 zip / 文件夹拖入窗口任意位置安装（身份以 Info.json 的 Id 为准）":
            "Or drop a mod zip / folder anywhere in this window to install (identity = the Id in Info.json)",
        "游戏目录:": "Game directory:", "未选择": "Not set",
        "搜索": "Search",
        "全局搜索本机的 ADOFAI 安装目录":
            "Search this machine globally for ADOFAI installations",
        "正在全局搜索游戏目录…": "Searching for game directories…",
        "未选择游戏目录。": "No game directory selected.",
        "未找到游戏目录。": "No game directory found.",
        "UMM 运行时: {ver}": "UMM runtime: {ver}",
        "✓ 文件就绪": "✓ files ready",
        "✗ 缺失（先从 zip 安装）": "✗ missing (install from zip first)",
        "注入状态:": "Injection:",
        "✓ 已注入": "✓ injected", "未注入": "not injected",
        "原始备份:": "Original backup:",
        "✓ 存在": "✓ present", "✗ 不存在": "✗ missing",
        "入口程序集:": "Entry assembly:",
        "入口点:": "Entry point:",
        "注入 UMM": "Inject UMM", "卸载补丁": "Unpatch",
        "恢复原文件": "Restore original",
        "从 zip 安装 UMM 运行时…": "Install UMM runtime from zip…",
        "重新生成诊断": "Regenerate diagnostics",
        "游戏目录: {dir}": "Game directory: {dir}",
        "UMM 注入: {inj}  ·  Params.xml: {params}":
            "UMM injected: {inj}  ·  Params.xml: {params}",
        "已装模组 {n} 个  ·  游戏进程: {proc}":
            "{n} mods installed  ·  game process: {proc}",
        "运行中": "running", "未运行": "not running",
        "存在": "present", "不存在": "missing",
        "--- UMM Log.txt 末尾 {n} 行 ---": "--- last {n} lines of UMM Log.txt ---",
        "(读取失败: {ex})": "(failed to read: {ex})",
        "注意：这是 Windows 版安装，需经 Proton/Wine 运行；CoreModule 注入方式未在 Proton 下验证，模组管理功能不受影响。":
            "Note: this is a Windows build, run it via Proton/Wine. CoreModule injection is unverified under Proton; mod management is unaffected.",
        "选择…": "Browse…",
        "卸载模组「{name}」？": "Uninstall mod \"{name}\"?",
        "该模组文件夹将被移入系统回收站，可随时恢复。":
            "The mod folder will be moved to the system trash and can be restored anytime.",
        "取消": "Cancel",
        "卸载 UMM 注入补丁？": "Remove the UMM injection patch?",
        "仅移除启动桩，保留 UMM 文件与已装模组。重启游戏后生效。":
            "Only the starter stub is removed; UMM files and installed mods are kept. Takes effect after restarting the game.",
        "用原始备份完全恢复游戏程序集？":
            "Fully restore the game assembly from the original backup?",
        "UMM 与所有模组将不再加载（模组文件保留，可重新注入）。":
            "UMM and all mods will no longer load (mod files are kept; you can re-inject later).",
        "恢复": "Restore",
        "好": "OK",
        "无效的游戏目录": "Invalid game directory",
        "选择游戏安装目录": "Select game installation directory",
        "检测到多个 ADOFAI 安装目录，请选择要使用的：":
            "Multiple ADOFAI installations detected — pick the one to use:",
        "使用所选": "Use Selected",
        "选择 ADOFAI 游戏安装目录": "Select the ADOFAI game installation directory",
        "选择 UMM 模组 zip": "Select mod zip",
        "UMM 模组 (zip)": "UMM mod (zip)",
        "选择 UMM 运行时 zip": "Select UMM runtime zip",
        "UMM 运行时 (zip)": "UMM runtime (zip)",
        "未找到游戏目录": "No game directory found",
        "在常见路径、Steam 库与挂载点中均未找到 ADOFAI，请用「选择…」手动指定。":
            "ADOFAI was not found in common paths, Steam libraries or mount points — use \"Browse…\" to pick it manually.",
        "游戏已启动": "Game launched",
        "未找到游戏可执行文件": "Game executable not found",
        "未安装 UMM 运行时" : "UMM runtime not installed",
        "往游戏核心程序集嵌入启动桩（自动备份为 .original_），UMM 运行时文件缺失时请先从 zip 安装。":
            "Embeds a starter stub into the game's core assembly (auto-backed up as .original_). If UMM runtime files are missing, install them from a zip first.",
        "仅移除启动桩，保留 UMM 文件与模组。":
            "Removes only the starter stub; UMM files and mods are kept.",
        "用原始备份完全还原程序集，UMM 与模组将不再加载。":
            "Fully restores the assembly from the original backup; UMM and mods will no longer load.",
    },
    "ko": {
        # 핵심 ModManager 메시지
        "路径不存在": "경로가 존재하지 않습니다",
        "仅支持 .zip 压缩包或包含 Info.json 的文件夹":
            ".zip 압축 파일 또는 Info.json이 포함된 폴더만 지원됩니다",
        "zip 内未找到 Info.json（这看起来不是 UMM 模组包）":
            "zip에서 Info.json을 찾을 수 없습니다 (UMM 모드 패키지가 아닌 것 같습니다)",
        "Info.json 解析失败: {ex}": "Info.json 파싱 실패: {ex}",
        "Info.json 缺少合法的 Id 字段": "Info.json에 유효한 Id 필드가 없습니다",
        "不是有效的 zip 文件": "유효한 zip 파일이 아닙니다",
        "Info.json 所在层级为空": "Info.json이 있는 계층이 비어 있습니다",
        "检测到路径穿越条目，已中止: {n}": "경로 탈출 항목이 감지되어 중단했습니다: {n}",
        "已安装 {name} v{ver}{note}": "설치됨: {name} v{ver}{note}",
        "安装失败: {ex}": "설치 실패: {ex}",
        "Params.xml 尚未生成，请先启动一次游戏再操作开关":
            "Params.xml이 아직 생성되지 않았습니다. 게임을 한 번 실행한 뒤에 스위치를 조작하세요",
        "写入 Params.xml 失败: {ex}": "Params.xml 쓰기 실패: {ex}",
        "已启用": "활성화됨",
        "已禁用": "비활성화됨",
        "{state} {mod_id}{note}": "{state} {mod_id}{note}",
        "（注意：游戏正在运行，退出游戏时可能被覆盖）":
            " (주의: 게임이 실행 중이며 게임 종료 시 덮어쓰일 수 있습니다)",
        "（注意：游戏正在运行，重新启动游戏后生效）":
            " (주의: 게임이 실행 중입니다. 게임을 다시 시작하면 적용됩니다)",
        "模组目录不存在: {folder}": "모드 디렉터리가 없습니다: {folder}",
        "已卸载 {folder}{note}": "제거됨: {folder}{note}",
        "已注入 {entry_assembly}（入口 {entry_point}）{note}":
            "주입됨: {entry_assembly} (진입점 {entry_point}){note}",
        "已移除 UMM 注入补丁（UMM 文件保留）":
            "UMM 주입 패치가 제거되었습니다 (UMM 파일 유지)",
        "已用 .original_ 备份恢复原始程序集（UMM 与模组将不再加载）":
            ".original_ 백업으로 원본 어셈블리를 복구했습니다 (UMM과 모드는 더 이상 로드되지 않음)",
        "zip 内未找到 UnityModManager.dll（这是 UMM 发行包吗？）":
            "zip에서 UnityModManager.dll을 찾을 수 없습니다 (UMM 배포 패키지가 맞나요?)",
        "已安装 UMM 运行时（{count} 个文件）→ Managed/UnityModManager/":
            "UMM 런타임 설치됨 (파일 {count}개) → Managed/UnityModManager/",
        "未找到 dist/UMMInjector.exe 且自动编译失败 (需要 mono 与游戏内 dnlib.dll)":
            "dist/UMMInjector.exe를 찾을 수 없고 자동 컴파일도 실패했습니다 (mono와 게임 내 dnlib.dll 필요)",
        "运行注入器失败: {ex}": "인젝터 실행 실패: {ex}",
        "注入器无输出": "인젝터 출력이 없습니다",
        "Linux 原生版": "리눅스 네이티브",
        "Windows 版 (Proton/Wine)": "윈도우 빌드 (Proton/Wine)",
        "Linux + Windows 双版本": "리눅스 + 윈도우 듀얼 빌드",
        # CLI
        "[-] 未能识别 ADOFAI 游戏目录，请用 --game 指定或设置 ADOFAI_PATH。":
            "[-] ADOFAI 게임 디렉터리를 확인할 수 없습니다. --game으로 지정하거나 ADOFAI_PATH를 설정하세요.",
        "全局搜索到以下候选目录:": "전역 검색으로 다음 후보 디렉터리를 찾았습니다:",
        "请用 --game 指定其一，或直接运行 GUI 选择。":
            "그중 하나를 --game으로 지정하거나 GUI에서 직접 선택하세요.",
        "游戏: {dir}  (UMM 注入: {inj})": "게임: {dir}  (UMM 주입: {inj})",
        "是": "예", "否": "아니요",
        "共 {n} 个模组": "총 {n}개의 모드",
        "未安装 PyGObject，无法启动图形界面。":
            "PyGObject가 설치되어 있지 않아 GUI를 시작할 수 없습니다.",
        "Ubuntu/Debian: sudo apt install python3-gi gir1.2-gtk-4.0":
            "Ubuntu/Debian: sudo apt install python3-gi gir1.2-gtk-4.0",
        # GUI
        "Unity Mod Manager — ADOFAI 模组管理器":
            "Unity Mod Manager — ADOFAI 모드 관리자",
        "启动游戏": "게임 실행", "打开 Mods 目录": "Mods 폴더 열기",
        "模组": "모드", "日志": "로그", "安装器": "설치",
        "启用": "활성", "名称": "이름", "版本": "버전",
        "作者": "제작자", "文件夹": "폴더",
        "安装模组…": "모드 설치…", "打开文件夹": "폴더 열기",
        "卸载": "제거",
        "或将 Mod 的 zip / 文件夹拖入窗口任意位置安装（身份以 Info.json 的 Id 为准）":
            "또는 모드 zip / 폴더를 창 아무 곳에나 끌어다 놓으면 설치됩니다 (식별자는 Info.json의 Id 기준)",
        "游戏目录:": "게임 디렉터리:", "未选择": "선택 안 됨",
        "搜索": "검색",
        "全局搜索本机的 ADOFAI 安装目录":
            "이 컴퓨터에서 ADOFAI 설치 디렉터리를 전역 검색합니다",
        "正在全局搜索游戏目录…": "게임 디렉터리 전역 검색 중…",
        "未选择游戏目录。": "게임 디렉터리가 선택되지 않았습니다.",
        "未找到游戏目录。": "게임 디렉터리를 찾을 수 없습니다.",
        "UMM 运行时: {ver}": "UMM 런타임: {ver}",
        "✓ 文件就绪": "✓ 파일 준비됨",
        "✗ 缺失（先从 zip 安装）": "✗ 없음 (먼저 zip에서 설치하세요)",
        "注入状态:": "주입 상태:",
        "✓ 已注入": "✓ 주입됨", "未注入": "미주입",
        "原始备份:": "원본 백업:",
        "✓ 存在": "✓ 있음", "✗ 不存在": "✗ 없음",
        "入口程序集:": "진입 어셈블리:",
        "入口点:": "진입점:",
        "注入 UMM": "UMM 주입", "卸载补丁": "패치 제거",
        "恢复原文件": "원본 파일 복구",
        "从 zip 安装 UMM 运行时…": "zip에서 UMM 런타임 설치…",
        "重新生成诊断": "진단 다시 생성",
        "游戏目录: {dir}": "게임 디렉터리: {dir}",
        "UMM 注入: {inj}  ·  Params.xml: {params}":
            "UMM 주입: {inj}  ·  Params.xml: {params}",
        "已装模组 {n} 个  ·  游戏进程: {proc}":
            "설치된 모드 {n}개  ·  게임 프로세스: {proc}",
        "运行中": "실행 중", "未运行": "실행 안 됨",
        "存在": "있음", "不存在": "없음",
        "--- UMM Log.txt 末尾 {n} 行 ---": "--- UMM Log.txt 마지막 {n}줄 ---",
        "(读取失败: {ex})": "(읽기 실패: {ex})",
        "注意：这是 Windows 版安装，需经 Proton/Wine 运行；CoreModule 注入方式未在 Proton 下验证，模组管理功能不受影响。":
            "참고: Windows 버전 설치이므로 Proton/Wine으로 실행해야 합니다. CoreModule 주입 방식은 Proton에서 검증되지 않았지만 모드 관리 기능은 영향을 받지 않습니다.",
        "选择…": "선택…",
        "卸载模组「{name}」？": "모드 \"{name}\"을(를) 제거할까요?",
        "该模组文件夹将被移入系统回收站，可随时恢复。":
            "모드 폴더는 시스템 휴지통으로 이동되며 언제든지 복구할 수 있습니다.",
        "取消": "취소",
        "卸载 UMM 注入补丁？": "UMM 주입 패치를 제거할까요?",
        "仅移除启动桩，保留 UMM 文件与已装模组。重启游戏后生效。":
            "스타터만 제거하며 UMM 파일과 설치된 모드는 유지됩니다. 게임 재시작 후 적용됩니다.",
        "用原始备份完全恢复游戏程序集？":
            "원본 백업으로 게임 어셈블리를 완전히 복구할까요?",
        "UMM 与所有模组将不再加载（模组文件保留，可重新注入）。":
            "UMM과 모든 모드는 더 이상 로드되지 않습니다 (모드 파일은 유지되며 다시 주입할 수 있습니다).",
        "恢复": "복구",
        "好": "확인",
        "无效的游戏目录": "잘못된 게임 디렉터리",
        "选择游戏安装目录": "게임 설치 디렉터리 선택",
        "检测到多个 ADOFAI 安装目录，请选择要使用的：":
            "여러 ADOFAI 설치 디렉터리가 감지되었습니다. 사용할 디렉터리를 선택하세요:",
        "使用所选": "선택 항목 사용",
        "选择 ADOFAI 游戏安装目录": "ADOFAI 게임 설치 디렉터리 선택",
        "选择 UMM 模组 zip": "UMM 모드 zip 선택",
        "UMM 模组 (zip)": "UMM 모드 (zip)",
        "选择 UMM 运行时 zip": "UMM 런타임 zip 선택",
        "UMM 运行时 (zip)": "UMM 런타임 (zip)",
        "未找到游戏目录": "게임 디렉터리를 찾을 수 없음",
        "在常见路径、Steam 库与挂载点中均未找到 ADOFAI，请用「选择…」手动指定。":
            "일반 경로, Steam 라이브러리, 마운트 지점에서 ADOFAI를 찾지 못했습니다. 「선택…」으로 직접 지정해 주세요.",
        "游戏已启动": "게임이 시작되었습니다",
        "未找到游戏可执行文件": "게임 실행 파일을 찾을 수 없습니다",
        "未安装 UMM 运行时": "UMM 런타임이 설치되어 있지 않습니다",
        "往游戏核心程序集嵌入启动桩（自动备份为 .original_），UMM 运行时文件缺失时请先从 zip 安装。":
            "게임 핵심 어셈블리에 스타터를 삽입합니다 (.original_ 자동 백업). UMM 런타임 파일이 없으면 먼저 zip에서 설치하세요.",
        "仅移除启动桩，保留 UMM 文件与模组。":
            "스타터만 제거하며 UMM 파일과 모드는 유지됩니다.",
        "用原始备份完全还原程序集，UMM 与模组将不再加载。":
            "원본 백업으로 어셈블리를 완전히 되돌립니다. UMM과 모드는 더 이상 로드되지 않습니다.",
    },
}


def _detect_lang() -> str:
    cfg = load_config()
    if cfg.get("lang") in SUPPORTED_LANGS:
        return cfg["lang"]
    env = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES")
           or os.environ.get("LANG") or "").lower()
    for prefix in SUPPORTED_LANGS:
        if env.startswith(prefix):
            return prefix
    return "zh"


_current_lang = [None]  # 列表包装以便在函数内赋值


def tr(key: str, **kw) -> str:
    if _current_lang[0] is None:
        _current_lang[0] = _detect_lang()
    text = STRINGS.get(_current_lang[0], {}).get(key)
    if text is None:
        text = key  # 中文原文即兜底
    return text.format(**kw) if kw else text


def set_lang(lang: str):
    if lang in SUPPORTED_LANGS:
        _current_lang[0] = lang
        cfg = load_config()
        cfg["lang"] = lang
        save_config(cfg)


def type_tag(game_dir) -> str:
    """构建类型的本地化标签（GUI / CLI 展示用）。"""
    return tr({
        "linux": "Linux 原生版",
        "windows": "Windows 版 (Proton/Wine)",
        "both": "Linux + Windows 双版本",
    }.get(detect_build_type(game_dir), ""))


# ---------------------------------------------------------------- 底层逻辑

def find_info_json(directory: Path) -> Optional[Path]:
    """在模组目录中查找 Info.json（大小写不敏感）。"""
    if not directory.is_dir():
        return None
    for f in sorted(directory.iterdir()):
        if f.is_file() and f.name.lower() == "info.json":
            return f
    return None


def game_running() -> bool:
    """检测游戏进程是否正在运行（运行中改 Params 会被游戏退出时覆盖）。

    用 /proc/*/comm 而不是 pgrep -f：后者会把命令行里恰好含有游戏名字符串的
    其它进程（包括调用者自己的 shell）误判为游戏。
    """
    try:
        for p in Path("/proc").iterdir():
            if not p.name.isdigit():
                continue
            try:
                comm = (p / "comm").read_text().strip()
            except OSError:
                continue
            # Linux comm 最长 15 字符，长名会被截断
            if comm in (GAME_PROCESS_HINT, GAME_PROCESS_HINT[:15]):
                return True
    except Exception:
        pass
    return False


class ModManager:
    def __init__(self, game_dir: Path):
        self.game_dir = Path(game_dir).resolve()
        self.managed = get_managed_dir(self.game_dir)
        if not self.managed:
            raise RuntimeError(f"在 {self.game_dir} 中未找到 Managed 目录")
        self.mods_dir = self.game_dir / "Mods"
        self.params_xml = self.managed / "UnityModManager" / "Params.xml"
        self.umm_dll = self.managed / "UnityModManager" / "UnityModManager.dll"

    # ---- 状态 ----

    def is_injected(self) -> bool:
        """检查 UMM 是否已注入 CoreModule（流式扫描，不整读大文件）。"""
        core = self.managed / "UnityEngine.CoreModule.dll"
        if not core.is_file():
            return False
        try:
            tail = b""
            with open(core, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    if b"UnityModManager" in tail + chunk:
                        return True
                    tail = chunk[-64:]
        except Exception:
            pass
        return False

    def read_enabled_map(self) -> Dict[str, bool]:
        """从 Params.xml 读取各模组的 Enabled 状态（缺省视为启用）。"""
        if not self.params_xml.is_file():
            return {}
        try:
            root = ET.parse(self.params_xml).getroot()
        except Exception:
            return {}
        out = {}
        for m in root.iter("Mod"):
            mid = m.get("Id")
            if mid:
                out[mid] = m.get("Enabled") != "false"
        return out

    def list_mods(self) -> List[dict]:
        enabled_map = self.read_enabled_map()
        mods = []
        if not self.mods_dir.is_dir():
            return mods
        for d in sorted(self.mods_dir.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            info = find_info_json(d)
            if info is None:
                continue
            try:
                data = json.loads(info.read_text(encoding="utf-8-sig"))
            except Exception:
                data = {}
            mod_id = str(data.get("Id") or d.name)
            mods.append({
                "id": mod_id,
                "display": str(data.get("DisplayName") or mod_id),
                "version": str(data.get("Version") or "?"),
                "author": str(data.get("Author") or ""),
                "folder": d.name,
                "enabled": enabled_map.get(mod_id, True),
            })
        return mods

    # ---- 安装 ----

    def install(self, source: Path) -> Tuple[bool, str]:
        """安装 zip 或文件夹形式的 UMM 模组。身份以 Info.json 的 Id 为准。"""
        source = Path(source).expanduser()
        if not source.exists():
            return False, tr("路径不存在")
        self.mods_dir.mkdir(parents=True, exist_ok=True)
        try:
            if source.is_dir():
                return self._install_from_dir(source)
            if source.suffix.lower() != ".zip":
                return False, tr("仅支持 .zip 压缩包或包含 Info.json 的文件夹")
            with zipfile.ZipFile(source) as zf:
                names = [n.replace("\\", "/") for n in zf.namelist()]
                infos = sorted(
                    (n for n in names
                     if not n.endswith("/") and os.path.basename(n).lower() == "info.json"),
                    key=lambda n: (n.count("/"), len(n)))
                if not infos:
                    return False, tr("zip 内未找到 Info.json（这看起来不是 UMM 模组包）")
                info_path = infos[0]
                try:
                    data = json.loads(zf.read(info_path).decode("utf-8-sig"))
                except Exception as ex:
                    return False, tr("Info.json 解析失败: {ex}", ex=ex)
                mod_id, ok, msg = self._validate_id(data)
                if not ok:
                    return False, msg
                prefix = info_path[:-len("info.json")]
                return self._swap_in(lambda dst: self._extract_entries(zf, names, prefix, dst),
                                     mod_id, data)
        except zipfile.BadZipFile:
            return False, tr("不是有效的 zip 文件")

    def _validate_id(self, data: dict) -> Tuple[str, bool, str]:
        mod_id = str(data.get("Id", "")).strip()
        if not mod_id or mod_id in (".", "..") or any(c in mod_id for c in "/\\"):
            return "", False, tr("Info.json 缺少合法的 Id 字段")
        return mod_id, True, ""

    def _install_from_dir(self, src: Path) -> Tuple[bool, str]:
        info = find_info_json(src)
        if info is None:
            return False, tr("zip 内未找到 Info.json（这看起来不是 UMM 模组包）")
        try:
            data = json.loads(info.read_text(encoding="utf-8-sig"))
        except Exception as ex:
            return False, tr("Info.json 解析失败: {ex}", ex=ex)
        mod_id, ok, msg = self._validate_id(data)
        if not ok:
            return False, msg
        return self._swap_in(lambda dst: shutil.copytree(src, dst, dirs_exist_ok=True),
                             mod_id, data)

    def _extract_entries(self, zf: zipfile.ZipFile, names: List[str],
                         prefix: str, dst: Path) -> None:
        entries = [n for n in names
                   if n.startswith(prefix) and n != prefix and not n.endswith("/")]
        if not entries:
            raise RuntimeError(tr("Info.json 所在层级为空"))
        dst_root = str(dst.resolve()) + os.sep
        for n in entries:
            dest = (dst / n[len(prefix):]).resolve()
            if not str(dest).startswith(dst_root):
                raise RuntimeError(tr("检测到路径穿越条目，已中止: {n}", n=n))
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(n) as fin, open(dest, "wb") as fout:
                shutil.copyfileobj(fin, fout)

    def _swap_in(self, populate, mod_id: str, data: dict) -> Tuple[bool, str]:
        """先填充临时目录，成功后原子换入 Mods/<Id>，失败回滚旧版本。"""
        target = self.mods_dir / mod_id
        tmp = self.mods_dir / f".{mod_id}.tmp-{os.getpid()}"
        old = self.mods_dir / f".{mod_id}.old-{os.getpid()}"
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(old, ignore_errors=True)
        tmp.mkdir(parents=True)
        try:
            populate(tmp)
        except Exception as ex:
            shutil.rmtree(tmp, ignore_errors=True)
            return False, tr("安装失败: {ex}", ex=ex)
        if target.exists():
            target.rename(old)
        try:
            tmp.rename(target)
        except Exception as ex:
            if old.exists():
                old.rename(target)  # 回滚
            shutil.rmtree(tmp, ignore_errors=True)
            return False, tr("安装失败: {ex}", ex=ex)
        shutil.rmtree(old, ignore_errors=True)
        name = str(data.get("DisplayName") or mod_id)
        ver = str(data.get("Version") or "?")
        note = tr("（注意：游戏正在运行，重新启动游戏后生效）") if game_running() else ""
        return True, tr("已安装 {name} v{ver}{note}", name=name, ver=ver, note=note)

    # ---- 开关 ----

    def set_enabled(self, mod_id: str, enabled: bool) -> Tuple[bool, str]:
        if not self.params_xml.is_file():
            return False, tr("Params.xml 尚未生成，请先启动一次游戏再操作开关")
        try:
            tree = ET.parse(self.params_xml)
            root = tree.getroot()
            mod_params = root.find("ModParams")
            if mod_params is None:
                mod_params = ET.SubElement(root, "ModParams")
            entry = None
            for m in mod_params.findall("Mod"):
                if m.get("Id") == mod_id:
                    entry = m
                    break
            if entry is None:
                entry = ET.SubElement(mod_params, "Mod",
                                      {"Id": mod_id, "Enabled": "true"})
                hk = ET.SubElement(entry, "Hotkey")
                ET.SubElement(hk, "keyCode").text = "None"
                ET.SubElement(hk, "modifiers").text = "0"
            entry.set("Enabled", "true" if enabled else "false")
            tree.write(self.params_xml, encoding="utf-8", xml_declaration=True)
        except Exception as ex:
            return False, tr("写入 Params.xml 失败: {ex}", ex=ex)
        state = tr("已启用") if enabled else tr("已禁用")
        note = tr("（注意：游戏正在运行，退出游戏时可能被覆盖）") if game_running() else ""
        return True, tr("{state} {mod_id}{note}", state=state, mod_id=mod_id, note=note)

    # ---- 卸载 ----

    def remove_mod(self, folder: str) -> Tuple[bool, str]:
        target = self.mods_dir / folder
        if not target.is_dir() or target.parent != self.mods_dir:
            return False, tr("模组目录不存在: {folder}", folder=folder)
        try:
            from gi.repository import Gio  # GTK 环境下移入回收站，可恢复
            if not Gio.File.new_for_path(str(target)).trash():
                raise RuntimeError("trash() returned False")
        except Exception:
            shutil.rmtree(target)
        # 顺手清理 Params.xml 中的开关记录
        if self.params_xml.is_file():
            try:
                tree = ET.parse(self.params_xml)
                for parent in tree.getroot().iter("ModParams"):
                    for m in list(parent.findall("Mod")):
                        if m.get("Id") == folder:
                            parent.remove(m)
                tree.write(self.params_xml, encoding="utf-8", xml_declaration=True)
            except Exception:
                pass
        note = tr("（注意：游戏正在运行，重新启动游戏后生效）") if game_running() else ""
        return True, tr("已卸载 {folder}{note}", folder=folder, note=note)


    # ---- UMM 注入 (调用 dist/UMMInjector.exe, 源码见 src/UMMInjector.cs) ----

    INJECTOR_NAME = "UMMInjector.exe"

    @staticmethod
    def _injector_candidates() -> Tuple[Path, Path]:
        # deb 安装到 /usr 后仓库目录只读, 构建产物会落到用户数据目录
        return (Path(__file__).parent / "dist" / ModManager.INJECTOR_NAME,
                Path.home() / ".local/share/adofai-linux-fix/dist"
                / ModManager.INJECTOR_NAME)

    @property
    def injector_exe(self) -> Path:
        for cand in self._injector_candidates():
            if cand.is_file():
                return cand
        return self._injector_candidates()[0]

    def _build_injector(self) -> bool:
        script = Path(__file__).parent / "scripts" / "build_injector.sh"
        if not script.is_file():
            return False
        try:
            subprocess.run(["bash", str(script)], capture_output=True,
                           text=True, timeout=300, check=True)
            return any(c.is_file() for c in self._injector_candidates())
        except Exception:
            return False

    def _run_injector(self, command: str) -> Tuple[Optional[dict], str]:
        exe = self.injector_exe
        if not exe.is_file() and not self._build_injector():
            return None, tr("未找到 dist/UMMInjector.exe 且自动编译失败 (需要 mono 与游戏内 dnlib.dll)")
        try:
            # dnlib 随游戏内 UMM 分发 (deb 不打包): 经 MONO_PATH 让 mono 解析
            env = {**os.environ,
                   "MONO_PATH": str(self.managed / "UnityModManager")}
            r = subprocess.run(["mono", str(exe), command, str(self.game_dir)],
                               capture_output=True, text=True, timeout=120,
                               env=env)
        except Exception as ex:
            return None, tr("运行注入器失败: {ex}", ex=ex)
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line), ""
                except Exception:
                    pass
        out = (r.stdout or "") + (r.stderr or "")
        err = next((l for l in out.splitlines() if l.startswith("ERR:")), None)
        return None, (err or out.strip()[:400] or tr("注入器无输出"))

    def umm_status(self) -> dict:
        data, err = self._run_injector("status")
        return data if data is not None else {"error": err}

    def umm_inject(self) -> Tuple[bool, str]:
        data, err = self._run_injector("inject")
        if data is None:
            return False, err
        note = tr("（注意：游戏正在运行，重新启动游戏后生效）") if game_running() else ""
        return True, tr("已注入 {entry_assembly}（入口 {entry_point}）{note}",
                        entry_assembly=data['entry_assembly'],
                        entry_point=data['entry_point'], note=note)

    def umm_unpatch(self) -> Tuple[bool, str]:
        data, err = self._run_injector("unpatch")
        if data is None:
            return False, err
        return True, tr("已移除 UMM 注入补丁（UMM 文件保留）")

    def umm_restore(self) -> Tuple[bool, str]:
        data, err = self._run_injector("restore")
        if data is None:
            return False, err
        return True, tr("已用 .original_ 备份恢复原始程序集（UMM 与模组将不再加载）")

    def install_umm_zip(self, zip_path: Path) -> Tuple[bool, str]:
        """解压 UMM 运行时 zip 到 Managed/UnityModManager/（用于全新安装）。"""
        try:
            with zipfile.ZipFile(zip_path) as zf:
                names = [n.replace("\\", "/") for n in zf.namelist()]
                dlls = sorted((n for n in names if n.endswith("UnityModManager.dll")),
                              key=lambda n: (n.count("/"), len(n)))
                if not dlls:
                    return False, tr("zip 内未找到 UnityModManager.dll（这是 UMM 发行包吗？）")
                base = dlls[0][:-len("UnityModManager.dll")]
                target = self.managed / "UnityModManager"
                target.mkdir(parents=True, exist_ok=True)
                target_root = str(target.resolve()) + os.sep
                count = 0
                for n in names:
                    if not n.startswith(base) or n.endswith("/"):
                        continue
                    dest = (target / n[len(base):]).resolve()
                    if not str(dest).startswith(target_root):
                        return False, tr("检测到路径穿越条目，已中止: {n}", n=n)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(n) as fin, open(dest, "wb") as fout:
                        shutil.copyfileobj(fin, fout)
                    count += 1
            return True, tr("已安装 UMM 运行时（{count} 个文件）→ Managed/UnityModManager/",
                            count=count)
        except zipfile.BadZipFile:
            return False, tr("不是有效的 zip 文件")


# ---------------------------------------------------------------- GTK4 界面

def run_gui(game_dir: Path) -> int:
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)  # GTK4 遗留 API 警告
    try:
        import gi
    except ImportError:
        print(f"{C_RED}[-] {tr('未安装 PyGObject，无法启动图形界面。')}{C_RESET}")
        print(f"    {tr('Ubuntu/Debian: sudo apt install python3-gi gir1.2-gtk-4.0')}")
        return 1
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, Gio, GLib, Gtk

    import time
    import threading

    mgr = None  # ModManager 实例; 未选择游戏目录时为 None

    class App(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="io.github.hoshigt.adofai-modmgr")
            self._pending_remove = None
            self._search_auto = False

        def set_game_dir(self, path):
            """切换游戏目录并刷新全部页面（无效目录弹提示并保留原目录）。"""
            nonlocal mgr
            try:
                new_mgr = ModManager(Path(path).expanduser().resolve())
            except RuntimeError as ex:
                self._alert(tr("无效的游戏目录"), str(ex))
                return
            mgr = new_mgr
            save_game_dir(mgr.game_dir)
            self.dir_path_label.set_text(
                str(mgr.game_dir) + self._type_suffix())
            if detect_build_type(mgr.game_dir) == "windows":
                self.log(tr("注意：这是 Windows 版安装，需经 Proton/Wine 运行；"
                            "CoreModule 注入方式未在 Proton 下验证，模组管理功能不受影响。"))
            self.populate_diagnostics()
            self.refresh()
            self.refresh_umm_status()

        def _alert(self, title, detail=""):
            dialog = Gtk.AlertDialog()
            dialog.set_message(title)
            if detail:
                dialog.set_detail(detail)
            dialog.set_buttons([tr("好")])
            dialog.choose(self.win, None, lambda d, r: None)

        def on_select_game_dir(self, *args):
            dialog = Gtk.FileDialog(title=tr("选择 ADOFAI 游戏安装目录"))
            dialog.select_folder(self.win, None, self.on_select_game_dir_done)

        def on_select_game_dir_done(self, dialog, result):
            try:
                folder = dialog.select_folder_finish(result)
            except GLib.Error:
                return  # 用户取消
            if folder:
                self.set_game_dir(Path(folder.get_path()))

        # ---- 全局搜索 ----

        def on_search_game_dir(self, *args, _auto=False):
            """后台线程全局扫描本机的 ADOFAI 安装目录。"""
            self.btn_search_dir.set_sensitive(False)
            self.dir_path_label.set_text("正在全局搜索游戏目录…")
            self._search_auto = _auto

            def worker():
                dirs = find_all_adofai_dirs()
                GLib.idle_add(self._scan_done, dirs)

            threading.Thread(target=worker, daemon=True).start()

        def _scan_done(self, dirs):
            self.btn_search_dir.set_sensitive(True)
            if len(dirs) == 1:
                self.set_game_dir(dirs[0])
            elif len(dirs) > 1:
                self._show_dir_chooser(dirs)
            else:
                self.dir_path_label.set_text(tr("未选择"))
                self.umm_label.set_markup(
                    f"<span foreground='#e01b24'>{tr('未找到游戏目录。')}</span>")
                if not self._search_auto:
                    self._alert(tr("未找到游戏目录"),
                                tr("在常见路径、Steam 库与挂载点中均未找到 ADOFAI，"
                                   "请用「选择…」手动指定。"))
            return GLib.SOURCE_REMOVE

        def _show_dir_chooser(self, dirs):
            dialog = Gtk.Dialog(title=tr("选择游戏安装目录"),
                                transient_for=self.win, modal=True)
            dialog.set_default_size(620, 300)
            dialog.add_button(tr("取消"), Gtk.ResponseType.CANCEL)
            ok = dialog.add_button(tr("使用所选"), Gtk.ResponseType.OK)
            ok.add_css_class("suggested-action")

            area = dialog.get_content_area()
            area.set_spacing(8)
            area.set_margin_top(10)
            area.set_margin_bottom(10)
            area.set_margin_start(10)
            area.set_margin_end(10)
            area.append(Gtk.Label(
                label=tr("检测到多个 ADOFAI 安装目录，请选择要使用的："), xalign=0))
            listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
            for d in dirs:
                row = Gtk.ListBoxRow()
                label = Gtk.Label(xalign=0, ellipsize=3,
                                  margin_top=5, margin_bottom=5,
                                  margin_start=6, margin_end=6)
                tag = type_tag(d)
                esc = GLib.markup_escape_text
                label.set_text(f"{esc(str(d))}"
                               + (f"\n<small>（{esc(tag)}）</small>" if tag else ""))
                label.set_use_markup(True)
                row.set_child(label)
                row.game_path = str(d)  # 选择框展示带标签, 真实路径挂 row 上
                listbox.append(row)
            listbox.select_row(listbox.get_row_at_index(0))
            ok.set_sensitive(True)
            listbox.connect("selected-rows-changed",
                            lambda lb: ok.set_sensitive(lb.get_selected_row() is not None))
            listbox.connect("row-activated",
                            lambda lb, row: dialog.response(Gtk.ResponseType.OK))
            area.append(Gtk.ScrolledWindow(vexpand=True, hexpand=True,
                                           child=listbox))

            def on_response(dlg, resp):
                row = listbox.get_selected_row()
                dlg.destroy()
                path = getattr(row, "game_path", None) if row is not None else None
                if resp == Gtk.ResponseType.OK and path:
                    self.set_game_dir(Path(path))
                elif resp == Gtk.ResponseType.CANCEL and self._search_auto:
                    self.on_select_game_dir()  # 启动时取消选择 → 手动指定

            dialog.connect("response", on_response)
            dialog.present()

        def do_activate(self):
            self._build_window()
            if mgr is None:
                if game_dir:
                    self.set_game_dir(game_dir)
                else:
                    self.on_search_game_dir(_auto=True)

        def _build_window(self):
            if _current_lang[0] is None:
                _current_lang[0] = _detect_lang()
            self._rebuilding = False
            self.win = Gtk.ApplicationWindow(
                application=self,
                title=tr("Unity Mod Manager — ADOFAI 模组管理器"),
                default_width=820, default_height=640)

            hb = Gtk.HeaderBar()
            self.lang_dd = Gtk.DropDown.new_from_strings(
                [{"zh": "中文", "en": "English", "ko": "한국어"}[l]
                 for l in SUPPORTED_LANGS])
            self.lang_dd.set_selected(list(SUPPORTED_LANGS).index(_current_lang[0]))
            self.lang_dd.connect("notify::selected", self.on_lang_changed)
            hb.pack_start(self.lang_dd)
            run_btn = Gtk.Button(icon_name="media-playback-start-symbolic",
                                 tooltip_text=tr("启动游戏"))
            run_btn.connect("clicked", self.on_launch_game)
            open_btn = Gtk.Button(icon_name="folder-open-symbolic",
                                  tooltip_text=tr("打开 Mods 目录"))
            open_btn.connect("clicked", self.on_open_dir)
            hb.pack_end(open_btn)
            hb.pack_end(run_btn)
            self.win.set_titlebar(hb)

            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                           margin_top=8, margin_bottom=10,
                           margin_start=10, margin_end=10, spacing=6)
            self.win.set_child(root)

            self.notebook = Gtk.Notebook(vexpand=True, hexpand=True)
            root.append(self.notebook)

            # ================= 模组页 (仿 UMM 安装器 Mods 标签) =================
            mods_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

            # 多列模组列表: 启用 | 名称 | 版本 | 作者 | 文件夹
            # ListStore 列: 0启用 1名称 2版本 3作者 4文件夹 5Id
            self.store = Gtk.ListStore(bool, str, str, str, str, str)
            self.tree = Gtk.TreeView(model=self.store)
            self.tree.get_selection().connect("changed", self.on_selection_changed)

            toggle_cell = Gtk.CellRendererToggle()
            toggle_cell.connect("toggled", self.on_toggle)
            col = Gtk.TreeViewColumn(tr("启用"), toggle_cell, active=0)
            col.set_fixed_width(48)
            col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            self.tree.append_column(col)

            for i, title, minw in ((1, tr("名称"), 190), (2, tr("版本"), 70),
                                   (3, tr("作者"), 150), (4, tr("文件夹"), 160)):
                cell = Gtk.CellRendererText(ellipsize=3)
                col = Gtk.TreeViewColumn(title, cell, text=i)
                col.set_resizable(True)
                col.set_min_width(minw)
                col.set_sort_column_id(i)
                self.tree.append_column(col)

            mods_page.append(Gtk.ScrolledWindow(vexpand=True, hexpand=True,
                                                child=self.tree))

            # 操作按钮排 (对应安装器底部 Install Mod 面板)
            btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            self.btn_install = Gtk.Button(label=tr("安装模组…"))
            self.btn_install.add_css_class("suggested-action")
            self.btn_install.connect("clicked", self.on_pick_file)
            btns.append(self.btn_install)
            self.btn_folder = Gtk.Button(label=tr("打开文件夹"), sensitive=False)
            self.btn_folder.connect("clicked", self.on_open_mod_dir)
            btns.append(self.btn_folder)
            self.btn_remove = Gtk.Button(label=tr("卸载"), sensitive=False)
            self.btn_remove.add_css_class("destructive-action")
            self.btn_remove.connect("clicked", self.on_remove)
            btns.append(self.btn_remove)
            hint = Gtk.Label(xalign=1, hexpand=True)
            hint.set_markup(
                "<small>" + tr("或将 Mod 的 zip / 文件夹拖入窗口任意位置安装"
                               "（身份以 Info.json 的 Id 为准）") + "</small>")
            btns.append(hint)
            mods_page.append(btns)

            self.status_label = Gtk.Label(xalign=0, wrap=True)
            mods_page.append(self.status_label)

            self.notebook.append_page(mods_page, Gtk.Label(label=tr("模组")))

            # ================= 日志页 (仿安装器底部 Log 面板) =================
            log_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            self.log_view = Gtk.TextView(editable=False, cursor_visible=False,
                                         top_margin=6, bottom_margin=6,
                                         left_margin=8, right_margin=8)
            self.log_view.add_css_class("monospace")
            log_page.append(Gtk.ScrolledWindow(vexpand=True, hexpand=True,
                                               child=self.log_view))
            log_btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            diag_btn = Gtk.Button(label=tr("重新生成诊断"))
            diag_btn.connect("clicked", lambda b: self.populate_diagnostics())
            log_btns.append(diag_btn)
            log_page.append(log_btns)
            self.notebook.append_page(log_page, Gtk.Label(label=tr("日志")))

            # ============ 安装器页 (仿 UMM 安装器 Install 标签) ============
            inst_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                spacing=10, margin_top=10, margin_start=4,
                                margin_end=4)

            # 游戏目录选择 (对应官方安装器的 Folder + Select)
            dir_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            dir_row.append(Gtk.Label(label=tr("游戏目录:"), valign=Gtk.Align.CENTER))
            self.dir_path_label = Gtk.Label(xalign=0, hexpand=True,
                                            ellipsize=3, valign=Gtk.Align.CENTER)
            self.dir_path_label.set_text(tr("未选择"))
            dir_row.append(self.dir_path_label)
            pick_dir = Gtk.Button(label=tr("选择…"))
            pick_dir.connect("clicked", self.on_select_game_dir)
            dir_row.append(pick_dir)
            self.btn_search_dir = Gtk.Button(label=tr("搜索"),
                                             tooltip_text=tr("全局搜索本机的 ADOFAI 安装目录"))
            self.btn_search_dir.connect("clicked", self.on_search_game_dir)
            dir_row.append(self.btn_search_dir)
            inst_page.append(dir_row)

            self.umm_label = Gtk.Label(xalign=0, wrap=True)
            self.umm_label.set_markup(
                f"<span foreground='#e01b24'>{tr('未选择游戏目录。')}</span>")
            inst_page.append(self.umm_label)

            note = Gtk.Label(xalign=0, wrap=True)
            note.set_markup(
                "<small>"
                f"<b>{tr('注入 UMM')}</b>：{tr('往游戏核心程序集嵌入启动桩（自动备份为 .original_），UMM 运行时文件缺失时请先从 zip 安装。')}\n"
                f"<b>{tr('卸载补丁')}</b>：{tr('仅移除启动桩，保留 UMM 文件与模组。')}\n"
                f"<b>{tr('恢复原文件')}</b>：{tr('用原始备份完全还原程序集，UMM 与模组将不再加载。')}"
                "</small>")
            inst_page.append(note)

            ibtns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            self.btn_umm_inject = Gtk.Button(label=tr("注入 UMM"))
            self.btn_umm_inject.add_css_class("suggested-action")
            self.btn_umm_inject.connect("clicked", self.on_umm_inject)
            ibtns.append(self.btn_umm_inject)
            self.btn_umm_unpatch = Gtk.Button(label=tr("卸载补丁"))
            self.btn_umm_unpatch.connect("clicked", self.on_umm_unpatch)
            ibtns.append(self.btn_umm_unpatch)
            self.btn_umm_restore = Gtk.Button(label=tr("恢复原文件"))
            self.btn_umm_restore.add_css_class("destructive-action")
            self.btn_umm_restore.connect("clicked", self.on_umm_restore)
            ibtns.append(self.btn_umm_restore)
            self.btn_umm_zip = Gtk.Button(label=tr("从 zip 安装 UMM 运行时…"))
            self.btn_umm_zip.connect("clicked", self.on_umm_zip)
            ibtns.append(self.btn_umm_zip)
            inst_page.append(ibtns)

            spacer = Gtk.Box(vexpand=True)
            inst_page.append(spacer)
            self.notebook.append_page(inst_page, Gtk.Label(label=tr("安装器")))

            # 整个窗口接收文件拖放
            self.drop_target = Gtk.DropTarget()
            self.drop_target.set_gtypes([Gdk.FileList, Gio.File])
            self.drop_target.set_actions(Gdk.DragAction.COPY)
            self.drop_target.connect("drop", self.on_drop)
            self.win.add_controller(self.drop_target)

            if mgr is not None:
                self.dir_path_label.set_text(
                    str(mgr.game_dir) + self._type_suffix())
                self.refresh()
                self.refresh_umm_status()
            self.win.present()

        def on_lang_changed(self, dd, pspec):
            if getattr(self, "_rebuilding", False):
                return
            lang = list(SUPPORTED_LANGS)[dd.get_selected()]
            if lang == _current_lang[0]:
                return
            set_lang(lang)
            self._rebuilding = True
            self.win.destroy()
            self._build_window()  # 重建窗口让全部文案切换语言

        @staticmethod
        def _type_suffix() -> str:
            tag = type_tag(mgr.game_dir)
            return f"（{tag}）" if tag else ""

        # ---------------- 基础设施 ----------------

        def log(self, msg: str):
            buf = self.log_view.get_buffer()
            end = buf.get_end_iter()
            buf.insert(end, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.log_view.scroll_mark_onscreen(buf.get_insert())

        def set_status(self, text: str, ok: bool = True):
            color = "#33d17a" if ok else "#e01b24"
            self.status_label.set_markup(
                f"<span foreground='{color}'>{GLib.markup_escape_text(text)}</span>")
            self.log(text)

        def populate_diagnostics(self, *args):
            if mgr is None:
                return
            self.log(tr("游戏目录: {dir}", dir=mgr.game_dir))
            self.log(tr("UMM 注入: {inj}  ·  Params.xml: {params}",
                        inj=tr("是") if mgr.is_injected() else tr("否"),
                        params=tr("存在") if mgr.params_xml.is_file() else tr("不存在")))
            self.log(tr("已装模组 {n} 个  ·  游戏进程: {proc}",
                        n=len(mgr.list_mods()),
                        proc=tr("运行中") if game_running() else tr("未运行")))
            log_txt = mgr.managed / "UnityModManager" / "Log.txt"
            if log_txt.is_file():
                self.log(tr("--- UMM Log.txt 末尾 {n} 行 ---", n=min(20, 1 << 30)))
                try:
                    lines = log_txt.read_text(encoding="utf-8",
                                              errors="replace").splitlines()
                    for line in lines[-20:]:
                        self.log("    " + line)
                except Exception as ex:
                    self.log(tr("(读取失败: {ex})", ex=ex))

        # ---------------- 模组列表 ----------------

        def refresh(self):
            if mgr is None:
                return
            self.store.clear()
            for m in mgr.list_mods():
                self.store.append([m["enabled"], m["display"], m["version"],
                                   m["author"], m["folder"], m["id"]])

        def selected_mod(self):
            model, it = self.tree.get_selection().get_selected()
            if it is None:
                return None
            return {"enabled": model[it][0], "display": model[it][1],
                    "version": model[it][2], "author": model[it][3],
                    "folder": model[it][4], "id": model[it][5]}

        def on_selection_changed(self, selection):
            has = self.selected_mod() is not None
            self.btn_folder.set_sensitive(has)
            self.btn_remove.set_sensitive(has)

        def on_toggle(self, cell, path):
            it = self.store.get_iter(path)
            mod_id = self.store[it][5]
            new_state = not self.store[it][0]
            ok, msg = mgr.set_enabled(mod_id, new_state)
            self.set_status(msg, ok)
            self.store[it][0] = new_state if ok else (not new_state)

        # ---------------- 动作 ----------------

        def on_drop(self, target, value, x, y):
            if isinstance(value, Gdk.FileList):
                files = list(value.get_files())
            elif isinstance(value, Gio.File):
                files = [value]
            else:
                files = []
            if not files:
                return False
            results = []
            for f in files:
                ok, msg = mgr.install(Path(f.get_path()))
                results.append(("✓ " if ok else "✗ ") + msg)
            self.set_status("; ".join(results),
                            all(r.startswith("✓") for r in results))
            self.refresh()
            return True

        def on_pick_file(self, btn):
            dialog = Gtk.FileDialog(title=tr("选择 UMM 模组 zip"))
            store = Gio.ListStore.new(Gtk.FileFilter)
            ff = Gtk.FileFilter(name=tr("UMM 模组 (zip)"))
            ff.add_mime_type("application/zip")
            ff.add_pattern("*.zip")
            store.append(ff)
            dialog.set_filters(store)
            dialog.open(self.win, None, self.on_pick_done)

        def on_pick_done(self, dialog, result):
            try:
                file = dialog.open_finish(result)
            except GLib.Error:
                return  # 用户取消
            if file:
                ok, msg = mgr.install(Path(file.get_path()))
                self.set_status(msg, ok)
                self.refresh()

        def on_remove(self, btn):
            mod = self.selected_mod()
            if not mod:
                return
            self._pending_remove = mod["folder"]
            dialog = Gtk.AlertDialog()
            dialog.set_message(tr("卸载模组「{name}」？", name=mod['display']))
            dialog.set_detail(tr("该模组文件夹将被移入系统回收站，可随时恢复。"))
            dialog.set_buttons([tr("取消"), tr("卸载")])
            dialog.choose(self.win, None, self.on_remove_done)

        def on_remove_done(self, dialog, result):
            try:
                idx = dialog.choose_finish(result)
            except GLib.Error:
                return
            folder, self._pending_remove = self._pending_remove, None
            if idx != 1 or not folder:
                return
            ok, msg = mgr.remove_mod(folder)
            self.set_status(msg, ok)
            self.refresh()

        def on_open_mod_dir(self, btn):
            mod = self.selected_mod()
            if mod:
                Gtk.show_uri(self.win,
                             (mgr.mods_dir / mod["folder"]).as_uri(),
                             Gdk.CURRENT_TIME)

        def on_open_dir(self, btn):
            Gtk.show_uri(self.win, mgr.mods_dir.as_uri(), Gdk.CURRENT_TIME)

        def on_launch_game(self, btn):
            binary = None
            for cand in ("ADanceOfFireAndIce", "ADanceOfFireAndIce.x86_64"):
                p = mgr.game_dir / cand
                if p.is_file():
                    binary = p
                    break
            if binary is None:
                self.set_status(tr("未找到游戏可执行文件"), False)
                return
            subprocess.Popen([str(binary)], cwd=str(mgr.game_dir),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             start_new_session=True)
            self.set_status(tr("游戏已启动"))

        # ---------------- 安装器页 ----------------

        def refresh_umm_status(self):
            if mgr is None:
                return
            data = mgr.umm_status()
            if "error" in data:
                self.umm_label.set_markup(
                    "<span foreground='#e01b24'>"
                    + GLib.markup_escape_text(data["error"]) + "</span>")
                self.btn_umm_inject.set_sensitive(False)
                return
            esc = GLib.markup_escape_text
            injected = bool(data.get("injected"))
            backup = bool(data.get("backup"))
            umm_files = bool(data.get("umm_files"))
            inj_color = "#33d17a" if injected else "#e01b24"
            self.umm_label.set_markup(
                tr("UMM 运行时: {ver}", ver=esc(data.get('umm_version') or '?'))
                + f"  <span foreground='{'#33d17a' if umm_files else '#e01b24'}'>"
                + (tr("✓ 文件就绪") if umm_files else tr("✗ 缺失（先从 zip 安装）"))
                + "</span>\n"
                + tr("注入状态:") + " "
                + f"<span foreground='{inj_color}'>"
                + (tr("✓ 已注入") if injected else tr("未注入")) + "</span>"
                + "  ·  " + tr("原始备份:") + " "
                + (tr("✓ 存在") if backup else tr("✗ 不存在")) + "\n"
                + tr("入口程序集:") + f" <tt>{esc(data.get('entry_assembly') or '')}</tt>\n"
                + tr("入口点:") + f" <tt>{esc(data.get('entry_point') or '')}</tt>")
            self.btn_umm_inject.set_sensitive(umm_files)
            self.btn_umm_unpatch.set_sensitive(injected)
            self.btn_umm_restore.set_sensitive(backup)

        def on_umm_inject(self, btn):
            ok, msg = mgr.umm_inject()
            self.set_status(msg, ok)
            self.refresh_umm_status()

        def on_umm_unpatch(self, btn):
            dialog = Gtk.AlertDialog()
            dialog.set_message(tr("卸载 UMM 注入补丁？"))
            dialog.set_detail(tr("仅移除启动桩，保留 UMM 文件与已装模组。重启游戏后生效。"))
            dialog.set_buttons([tr("取消"), tr("卸载补丁")])
            dialog.choose(self.win, None, self.on_umm_unpatch_done)

        def on_umm_unpatch_done(self, dialog, result):
            try:
                if dialog.choose_finish(result) != 1:
                    return
            except GLib.Error:
                return
            ok, msg = mgr.umm_unpatch()
            self.set_status(msg, ok)
            self.refresh_umm_status()

        def on_umm_restore(self, btn):
            dialog = Gtk.AlertDialog()
            dialog.set_message(tr("用原始备份完全恢复游戏程序集？"))
            dialog.set_detail(tr("UMM 与所有模组将不再加载（模组文件保留，可重新注入）。"))
            dialog.set_buttons([tr("取消"), tr("恢复")])
            dialog.choose(self.win, None, self.on_umm_restore_done)

        def on_umm_restore_done(self, dialog, result):
            try:
                if dialog.choose_finish(result) != 1:
                    return
            except GLib.Error:
                return
            ok, msg = mgr.umm_restore()
            self.set_status(msg, ok)
            self.refresh_umm_status()

        def on_umm_zip(self, btn):
            dialog = Gtk.FileDialog(title=tr("选择 UMM 运行时 zip"))
            store = Gio.ListStore.new(Gtk.FileFilter)
            ff = Gtk.FileFilter(name=tr("UMM 运行时 (zip)"))
            ff.add_mime_type("application/zip")
            ff.add_pattern("*.zip")
            store.append(ff)
            dialog.set_filters(store)
            dialog.open(self.win, None, self.on_umm_zip_done)

        def on_umm_zip_done(self, dialog, result):
            try:
                file = dialog.open_finish(result)
            except GLib.Error:
                return
            if not file:
                return
            ok, msg = mgr.install_umm_zip(Path(file.get_path()))
            self.set_status(msg, ok)
            self.refresh_umm_status()

    raise SystemExit(App().run(None))



# ---------------------------------------------------------------- CLI

def resolve_game_dir(explicit: Optional[str]) -> Optional[Path]:
    for c in (explicit, os.environ.get("ADOFAI_PATH"), load_saved_game_dir(),
              find_adofai_dir()):
        if c and Path(c).is_dir():
            return Path(c).expanduser().resolve()
    return None


def cli_main(argv) -> int:
    parser = argparse.ArgumentParser(
        prog="adofai_modmgr.py",
        description="ADOFAI UMM 模组管理器（拖拽 GUI + CLI）")
    parser.add_argument("--game", metavar="DIR", help="游戏安装目录（默认自动检测）")
    parser.add_argument("--list", action="store_true", help="列出已安装模组")
    parser.add_argument("--install", metavar="ZIP_OR_DIR", help="安装模组")
    parser.add_argument("--toggle", nargs=2, metavar=("MOD_ID", "on|off"),
                        help="启用/禁用模组")
    parser.add_argument("--remove", metavar="FOLDER", help="卸载模组（文件夹名）")
    parser.add_argument("--umm", choices=["status", "inject", "unpatch", "restore"],
                        help="UMM 注入器操作")
    args = parser.parse_args(argv)

    cli_cmd = args.list or args.install or args.toggle or args.remove or args.umm
    game_dir = resolve_game_dir(args.game)

    if cli_cmd:
        if not game_dir:
            print(f"{C_RED}{tr('[-] 未能识别 ADOFAI 游戏目录，请用 --game 指定或设置 ADOFAI_PATH。')}{C_RESET}")
            candidates = find_all_adofai_dirs()
            if candidates:
                print(f"{C_YELLOW}{tr('全局搜索到以下候选目录:')}{C_RESET}")
                for c in candidates:
                    tag = type_tag(c)
                    print(f"  - {c}" + (f"（{tag}）" if tag else ""))
                print(tr("请用 --game 指定其一，或直接运行 GUI 选择。"))
            return 1
        try:
            mgr = ModManager(game_dir)
        except RuntimeError as ex:
            print(f"{C_RED}[-] {ex}{C_RESET}")
            return 1

    if args.list:
        mods = mgr.list_mods()
        print(f"{C_BOLD}{tr('游戏: {dir}  (UMM 注入: {inj})', dir=mgr.game_dir,
              inj=tr('是') if mgr.is_injected() else tr('否'))}{C_RESET}")
        for m in mods:
            state = (f"{C_GREEN}{tr('已启用')}{C_RESET}" if m["enabled"]
                     else f"{C_RED}{tr('已禁用')}{C_RESET}")
            print(f"  {state}  {m['display']}  v{m['version']}  "
                  f"{C_CYAN}[{m['folder']}]{C_RESET}  {m['author']}")
        print(tr("共 {n} 个模组", n=len(mods)))
        return 0

    if args.install:
        ok, msg = mgr.install(Path(args.install))
        print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}")
        return 0 if ok else 1

    if args.toggle:
        mod_id, state = args.toggle
        if state.lower() not in ("on", "off"):
            print(f"{C_RED}[-] 第二个参数应为 on 或 off{C_RESET}")
            return 1
        ok, msg = mgr.set_enabled(mod_id, state.lower() == "on")
        print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}")
        return 0 if ok else 1

    if args.umm:
        if args.umm == "status":
            data = mgr.umm_status()
            if "error" in data:
                print(f"{C_RED}[-] {data['error']}{C_RESET}")
                return 1
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0
        fn = {"inject": mgr.umm_inject, "unpatch": mgr.umm_unpatch,
              "restore": mgr.umm_restore}[args.umm]
        ok, msg = fn()
        print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}")
        return 0 if ok else 1

    if args.remove:
        ok, msg = mgr.remove_mod(args.remove)
        print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}")
        return 0 if ok else 1

    return run_gui(game_dir)


if __name__ == "__main__":
    sys.exit(cli_main(sys.argv[1:]))
