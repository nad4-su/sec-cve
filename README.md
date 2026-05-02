# CVE-2026-31431 운영 점검/IaC 키트

Linux Kernel `algif_aead` 로컬 권한 상승 취약점(Copy Fail)에 대해 서버 현황을 점검하고, Ubuntu 계열 서버에 안전한 mitigation을 적용하며, 서버 정보/조치 결과 보고서를 생성하는 최소 운영 키트입니다.

## 구성

```text
.
├── ansible/
│   ├── inventory.example.ini
│   └── playbooks/
│       └── cve-2026-31431-mitigate.yml
├── config/
│   └── servers.tsv             # 점검/조치 대상 서버 목록
├── reports/                    # 실행 결과 보고서 출력 위치
└── scripts/
    ├── 01-check-cve-2026-31431.sh
    ├── markdown_to_docx.py
    └── 02-remediate-cve-2026-31431.sh
```

## 대상 서버 목록

`config/servers.tsv` 형식:

```text
name<TAB>host<TAB>user<TAB>port<TAB>notes
example-server<TAB>203.0.113.10<TAB>ubuntu<TAB>22<TAB>Example Ubuntu server
```

현재 `config/servers.tsv`는 문서용 예시입니다. 실제 운영 서버 목록은 `config/servers.local.tsv`처럼 별도 파일로 두고 공개 저장소에는 올리지 마세요.

## 1차: 서버 리스트 기반 점검/보고서 생성

```bash
cd /home/nad4/workspace/cve-2026-31431-iac-kit
./scripts/01-check-cve-2026-31431.sh
```

로컬 서버만 점검:

```bash
./scripts/01-check-cve-2026-31431.sh --local
```

특정 서버 목록 파일 사용:

```bash
./scripts/01-check-cve-2026-31431.sh --servers ./config/servers.local.tsv
```

특정 서버만 점검:

```bash
./scripts/01-check-cve-2026-31431.sh --servers ./config/servers.local.tsv --target example-server
```

특정 SSH 키를 명시:

```bash
./scripts/01-check-cve-2026-31431.sh --servers ./config/servers.local.tsv --identity ~/.ssh/id_ed25519
```

또는:

```bash
SSH_IDENTITY_FILE=~/.ssh/id_ed25519 ./scripts/01-check-cve-2026-31431.sh --servers ./config/servers.local.tsv
```

키 인증 실패 시 비밀번호 프롬프트 허용:

```bash
./scripts/01-check-cve-2026-31431.sh --servers ./config/servers.local.tsv --target example-server --password
```

스크립트는 기본적으로 `BatchMode=yes`로 실행되어 비밀번호 프롬프트 없이 키 인증만 시도합니다. `--password`를 주면 `BatchMode=no`로 바꾸어 SSH password/keyboard-interactive 인증을 허용합니다. `host` 컬럼에는 IP뿐 아니라 `~/.ssh/config`의 `Host` alias도 사용할 수 있으므로, 서버별 `IdentityFile`을 이미 SSH config에 관리하고 있다면 alias를 넣는 방식이 가장 간단합니다.

생성물:

- `reports/CVE-2026-31431-inventory-<timestamp>.csv`
- `reports/CVE-2026-31431-inventory-<timestamp>.md`
- `reports/CVE-2026-31431-inventory-<timestamp>.docx`

`.docx` 파일은 `.md` 보고서를 Word OpenXML 문서로 변환한 공유용 문서입니다. Google Docs/Word에서 읽기 쉽도록 요약표는 표로 유지하고, 서버별 상세 판정은 넓은 8컬럼 표 대신 서버별 상세 블록으로 재배치합니다. 생성 보고서에는 내부 IP와 호스트명이 포함될 수 있으므로 `reports/` 아래 파일은 기본적으로 git 추적 대상에서 제외합니다.

보고서 주요 판정:

- `KISA 기준 영향 있음 - 긴급`: `algif_aead` 모듈이 현재 로드됨
- `KISA 기준 영향 있음 - 업데이트/재부팅 필요`: 차단 설정은 있으나 커널/kmod 업데이트 또는 재부팅 필요
- `KISA 기준 영향 있음 - 차단 설정 필요`: KISA 기준 영향 버전이며 모듈 로드 차단 설정 없음
- `KISA 기준 영향 있음 - 차단 적용됨`: KISA 기준 영향 버전이나 모듈 로드 차단 설정 있음
- `KISA 기준 영향 없음`: KISA 공지의 해결 버전 이상
- `확인 실패`: SSH 접속 또는 원격 명령 실행 실패

KISA 기준은 보호나라 `Linux Kernel 보안 업데이트 권고`의 영향받는 버전(`6.19.12 미만`, `6.18.22 미만`)과 해결 버전(`6.19.12 이상`, `6.18.22 이상`)을 사용합니다. 배포판 커널은 보안 패치가 백포트될 수 있으므로 `KISA 기준 영향 있음`은 운영 조치 대상 선별 기준으로 봅니다.

## 2차: 조치 스크립트

안전을 위해 실제 조치는 `--apply`가 있어야 실행됩니다.

특정 서버만 조치:

```bash
./scripts/02-remediate-cve-2026-31431.sh --apply --target example-server
```

특정 SSH 키를 명시:

```bash
./scripts/02-remediate-cve-2026-31431.sh --apply --target example-server --identity ~/.ssh/id_ed25519
```

키 인증 실패 시 비밀번호 프롬프트 허용:

```bash
./scripts/02-remediate-cve-2026-31431.sh --apply --target example-server --password
```

전체 서버 조치:

```bash
./scripts/02-remediate-cve-2026-31431.sh --apply
```

조치 후 재부팅까지 수행:

```bash
./scripts/02-remediate-cve-2026-31431.sh --apply --target example-server --reboot
```

조치 내용:

1. `apt-get update`
2. `kmod`, `linux-generic`, `linux-image-generic`, `linux-headers-generic` 업데이트
3. `/etc/modprobe.d/disable-algif_aead.conf` 생성/갱신
4. `algif_aead` 로드 중이면 `rmmod` 시도
5. 조치 후 상태 로그 기록
6. `--reboot` 지정 시 재부팅

생성물:

- `reports/CVE-2026-31431-remediation-<timestamp>.log`

## Ansible로 조치 적용

로컬 서버에 적용:

```bash
cd /home/nad4/workspace/cve-2026-31431-iac-kit
ansible-playbook -i 'localhost,' -c local ansible/playbooks/cve-2026-31431-mitigate.yml --ask-become-pass
```

원격 서버에 적용하려면 `ansible/inventory.example.ini`를 복사해 대상 서버를 넣고 실행합니다.

```bash
cp ansible/inventory.example.ini ansible/inventory.ini
vi ansible/inventory.ini
ansible-playbook -i ansible/inventory.ini ansible/playbooks/cve-2026-31431-mitigate.yml --ask-become-pass
```

## 판정 기준

- `algif_aead` 모듈이 로드되어 있지 않아야 합니다.
- `/etc/modprobe.d/disable-algif_aead.conf` 또는 동등한 설정으로 `install algif_aead /bin/false`가 있어야 합니다.
- Ubuntu 24.04 noble 기준 `kmod` mitigation 버전은 `31+20240202-2ubuntu7.2` 이상 계열입니다.
- 커널 업데이트가 설치된 뒤에도 실행 중 커널이 낮으면 재부팅이 필요할 수 있습니다.

## 주의

이 키트는 실제 권한상승 PoC를 실행하지 않습니다. 프로덕션 서버에서 exploit 재현은 위험하므로, 방어 상태 검증 방식으로 점검합니다.
조치 스크립트는 SSH와 대상 서버의 sudo 권한이 필요합니다.
