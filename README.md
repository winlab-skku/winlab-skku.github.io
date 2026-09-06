# WIn Lab website

정적 사이트. `build.py`가 `data/pubs.txt`와 `build.py` 안의 멤버/뉴스 데이터로 HTML을 생성합니다.

- `python3 build.py base` / `theme-a` / `theme-b` / `theme-c` → `variants/<이름>/` 에 빌드
- 디자인 확정 후: 선택한 `variants/<이름>/` 내용을 저장소 루트로 복사하면 됩니다
- 논문 추가: `data/pubs.txt` 한 줄 추가 후 빌드
- 멤버/뉴스: `build.py`의 `GRAD`, `UNDERGRAD`, `ALUMNI`, `NEWS` 수정 후 빌드
- 사진: `assets/photos/<영문이름-소문자>.jpg`
