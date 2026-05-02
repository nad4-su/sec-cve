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

생성물:

- `reports/CVE-2026-31431-inventory-<timestamp>.csv`
- `reports/CVE-2026-31431-inventory-<timestamp>.md`

주요 판정 상태:

- `MITIGATED`: 모듈 미로드 + mitigation 존재 + 관련 업데이트 없음
- `MITIGATED_UPDATE_PENDING`: mitigation 존재, 단 커널/kmod 업데이트 대기
- `FAIL_MODULE_LOADED`: 취약 모듈 로드 중
- `NO_MODULE_BUT_MITIGATION_MISSING`: 모듈은 미로드이나 차단 설정 없음
- `ERROR`: SSH/명령 실행 실패

## 2차: 조치 스크립트

안전을 위해 실제 조치는 `--apply`가 있어야 실행됩니다.

특정 서버만 조치:

```bash
./scripts/02-remediate-cve-2026-31431.sh --apply --target example-server
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
