import pytest

from app.agents.competency import (
    ManualProject,
    compute_gap,
    diagnose_competency,
    get_domain_overlay,
    get_grad_lab_cluster,
    list_domain_overlays,
    list_grad_lab_clusters,
)
from app.parser import TranscriptData


def test_diagnose_competency_counts_verified_from_taken_courses():
    # data/courses.json에서 "자료구조"는 competency_tags=["자료구조_알고리즘"]로 태깅되어 있음(Task 2-4)
    transcript = TranscriptData(courses=[{"name": "자료구조", "credit": 3, "category": "전공필수"}])
    result = diagnose_competency(transcript, projects=[], track="백엔드")
    assert result["자료구조_알고리즘"]["verified"] == 1.0
    assert result["웹_프론트엔드"]["verified"] == 0.0


def test_diagnose_competency_ignores_unmatched_course_names():
    transcript = TranscriptData(courses=[{"name": "존재하지않는과목", "credit": 3, "category": "전공선택"}])
    result = diagnose_competency(transcript, projects=[], track="백엔드")
    assert all(v["verified"] == 0.0 for v in result.values())


def test_diagnose_competency_applies_project_field_weight_with_self_report_discount():
    transcript = TranscriptData(courses=[])
    project = ManualProject(title="배달앱 클론 코딩", field="웹_백엔드", is_team=False)
    result = diagnose_competency(transcript, projects=[project], track="백엔드")
    # competency.yaml project_fields.웹_백엔드: {클라우드_인프라:0.6, 데이터베이스:0.5, 시스템_네트워크:0.3}
    # 자기신고 기본 가중치 0.5를 곱한다(설계: 검증 1.0 vs 자기신고 0.5)
    assert result["클라우드_인프라"]["self_reported"] == pytest.approx(0.6 * 0.5)
    assert result["데이터베이스"]["self_reported"] == pytest.approx(0.5 * 0.5)
    assert result["클라우드_인프라"]["verified"] == 0.0  # 자기신고는 verified를 건드리지 않음


def test_diagnose_competency_adds_team_bonus_for_team_projects():
    transcript = TranscriptData(courses=[])
    project = ManualProject(title="해커톤", field="웹_백엔드", is_team=True)
    result = diagnose_competency(transcript, projects=[project], track="백엔드")
    # team_bonus(협업_PM:0.5, 커뮤니케이션_문서화:0.3)는 이미 가산치로 설계된 값이라 추가 할인 없이 더한다
    assert result["협업_PM"]["self_reported"] == pytest.approx(0.5)
    assert result["커뮤니케이션_문서화"]["self_reported"] == pytest.approx(0.3)


def test_diagnose_competency_기타_필드는_LLM_없이_기여하지_않음():
    transcript = TranscriptData(courses=[])
    project = ManualProject(title="자유 주제 프로젝트", field="기타", is_team=False)
    result = diagnose_competency(transcript, projects=[project], track="백엔드")
    assert all(v["self_reported"] == 0.0 for v in result.values())


def test_diagnose_competency_returns_all_sixteen_competencies():
    # 13(기술) + 3(도메인 지식: 금융·핀테크/모빌리티·임베디드/공공정책·행정) = 16 (2026-08-20 개정)
    transcript = TranscriptData(courses=[])
    result = diagnose_competency(transcript, projects=[], track="백엔드")
    assert len(result) == 16


def test_diagnose_competency_raises_on_unknown_track():
    transcript = TranscriptData(courses=[])
    with pytest.raises(KeyError):
        diagnose_competency(transcript, projects=[], track="존재하지않는트랙")


def test_compute_gap_returns_target_minus_current_when_positive():
    vector = {"데이터베이스": {"verified": 0.0, "self_reported": 0.0}}
    gap = compute_gap(vector, track="백엔드")
    assert gap["데이터베이스"] == pytest.approx(0.9)  # competency.yaml 백엔드.데이터베이스 가중치


def test_compute_gap_is_zero_when_current_meets_or_exceeds_target():
    vector = {"데이터베이스": {"verified": 2.0, "self_reported": 0.0}}
    gap = compute_gap(vector, track="백엔드")
    assert gap["데이터베이스"] == 0.0


def test_compute_gap_skips_the_label_key_present_on_some_tracks():
    # AI_데이터/기획_PM/대학원_연구는 track dict에 'label' 문자열 키가 섞여 있다(경쟁·매핑용이 아님)
    gap = compute_gap({}, track="AI_데이터")
    assert "label" not in gap


def test_compute_gap_merges_domain_overlay_adding_new_domain_axis():
    overlay = get_domain_overlay("금융권")
    gap = compute_gap({}, track="백엔드", overlay=overlay)
    assert gap["금융_핀테크지식"] == pytest.approx(0.9)  # 역할 트랙엔 없던 축이 오버레이로 추가됨


def test_compute_gap_merge_takes_max_when_both_track_and_overlay_weight_same_axis():
    overlay = {"보안": 0.4}  # 백엔드 트랙 자체도 보안: 0.4
    gap_with_overlay = compute_gap({}, track="백엔드", overlay=overlay)
    gap_without_overlay = compute_gap({}, track="백엔드")
    assert gap_with_overlay["보안"] == gap_without_overlay["보안"]  # 겹치면 낮은 쪽에 끌려가지 않음


def test_list_domain_overlays_returns_all_three():
    assert set(list_domain_overlays()) == {"금융권", "자동차", "공공기관"}


def test_get_domain_overlay_returns_named_weights():
    overlay = get_domain_overlay("자동차")
    assert overlay["모빌리티_임베디드지식"] == pytest.approx(0.9)


def test_list_grad_lab_clusters_returns_all_five():
    assert len(list_grad_lab_clusters()) == 5


def test_get_grad_lab_cluster_returns_named_weights():
    cluster = get_grad_lab_cluster("AI_데이터_연구실")
    assert cluster["데이터_ML"] == pytest.approx(0.9)
