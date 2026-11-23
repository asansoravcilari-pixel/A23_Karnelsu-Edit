You are a senior Android kernel integration engineer with expertise in Samsung Snapdragon 680 SM-A235F, Linux 4.19.157, KernelSU direct hooks, APatch, module CRCs and Verified Boot.

TASK: Inspect this repository and implement a concrete, safe correction to the stock ABI compatibility verification/build process for firmware A235FXXSEEZB1, Android 14, bootloader binary B14.

Known facts:
- Both stock_baseline with KernelSU OFF and stock_ksu_directhooks produce identical OEM CRC discrepancies: qca_cld3_wlan.ko 138 mismatches and rdbg.ko 6 mismatches. KernelSU alone is not the cause.
- OEM Samsung CONFIG_MODULE_SIG_FORCE=y; original proprietary drivers are Samsung-signed. CRC equality alone is insufficient.
- APatch boot.img patch retains stock ABI but has unverified Samsung RKP/UH/KDP boot behavior and OEM AVB/SignerVer02 signatures; a static successful patch is not a boot test.
- Do not fabricate signatures, disable Samsung hardening, bypass ABI gates, or claim boot success.
- scripts/compare_oem_crc.py recently got a check for empty reference input; find and test other false positives.
- Two-profile kernel builds succeeded but OEM CRC gates failed.

Deliverables:
1) Read docs/A235F_ABI_GATE.md, scripts/build_stock_abi.sh, scripts/compare_oem_crc.py, and relevant references.
2) Implement reproducible safety fixes for verifier and automated unit tests. Validate missing module rows, unexpected modules, duplicated reference imports, missing mandatory symbols; reject false PASS with zero required symbols.
3) If exact reason for 144 mismatches can be established from repository evidence, document and implement a bounded correction. Otherwise state evidence gap and next exact action.
4) Run tests within runner, no flashing, no private firmware/key upload.
5) Write a Turkish codex-report.md listing code changes, actual test outputs and blockers. Distinguish static validity from successful real device boot.
6) Leave tracked/untracked source code changes in workspace for a git diff artifact.

NO MAGISK. No fake flash-safe status. Prefer concrete tested code to speculation.