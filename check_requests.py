#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import database


def _to_dict(row: object) -> dict:
    if isinstance(row, dict):
        return row
    if hasattr(row, 'keys'):
        return dict(row)  # type: ignore[call-overload]
    return {}


def check_requests() -> None:
    all_requests = [_to_dict(r) for r in database.get_material_requests()]
    print(f"Total toutes demandes: {len(all_requests)}")

    sept29_requests = [r for r in all_requests if r.get('request_date') == '2025-09-29']
    print(f"Demandes avec request_date = '2025-09-29': {len(sept29_requests)}")

    planning_requests = [_to_dict(r) for r in database.get_planning_data('2025-09-29')]
    print(f"Demandes via get_planning_data('2025-09-29'): {len(planning_requests)}")

    print("\nDemandes avec request_date = '2025-09-29':")
    for i, r in enumerate(sept29_requests):
        horaire = r.get('horaire') or 'Non défini'
        print(f"  {i+1}. {r.get('teacher_name')} - {r.get('class_name')} à {horaire}")

    print("\nDemandes via get_planning_data:")
    for i, r in enumerate(planning_requests):
        horaire = r.get('horaire') or 'Non défini'
        print(f"  {i+1}. {r.get('teacher_name')} - {r.get('class_name')} à {horaire}")


if __name__ == "__main__":
    check_requests()
