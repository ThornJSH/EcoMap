# 구현 계획 - 문서화 및 배포

## 목표
1.  사용자가 프로그램을 쉽게 이해하고 사용할 수 있도록 마크다운 형식의 매뉴얼(`README.md`)을 작성합니다.
2.  프로젝트 소스 코드를 GitHub에 업로드하기 위해 로컬 Git 저장소를 설정하고 커밋합니다.

## 세부 계획

### 1. 사용 설명서 작성 (`README.md`)
프로젝트 루트에 `README.md` 파일을 생성하고 다음 내용을 포함합니다:
-   **프로젝트 소개**: 생태도 그리기 프로그램의 목적과 기능 요약.
-   **설치 및 실행 방법**:
    -   `dist/Ecomap.exe` 실행 방법.
    -   Python 소스 코드로 실행하는 방법 (개발자용).
-   **사용법**:
    -   중심 인물 설정.
    -   인물 추가 (관계, 방향 설정).
    -   저장 및 불러오기.
    -   이미지 내보내기.
-   **제작자 정보**: welfareact.net 등.

### 2. GitHub 업로드 준비
`gh` CLI가 설치되어 있지 않으므로, 로컬에서 Git 저장소를 초기화하고 커밋한 뒤, 사용자가 직접 GitHub에 **EcoMap**이라는 이름의 저장소를 만들어 푸시할 수 있도록 안내합니다.

#### 작업 순서
1.  **Git 초기화**: `git init`
2.  **`.gitignore` 생성**: 불필요한 파일이 업로드되지 않도록 설정.
    -   포함: `__pycache__/`, `dist/`, `build/`, `*.spec`, `.env`, `*.db` (개인 데이터 보호)
3.  **파일 추가 및 커밋**:
    -   `git add .`
    -   `git commit -m "Initial commit: Ecomap Desktop Application"`
4.  **원격 저장소 연결 안내**:
    -   사용자에게 GitHub에서 **EcoMap**이라는 이름의 새 리포지토리를 생성하고 URL을 복사해오도록 요청.
    -   `git remote add origin https://github.com/<사용자ID>/EcoMap.git` 및 `git push` 명령어 안내.

## 검증 계획
-   `README.md` 파일이 생성되고 내용이 정확한지 확인.
-   `.git` 폴더가 생성되고, `.gitignore`가 올바르게 작동하여 불필요한 파일이 제외되었는지 확인 (`git status`로 확인).
