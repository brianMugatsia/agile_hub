path = 'apps/sales/views.py'
content = open(path, encoding='utf-8').read()

old_target = 'queryset = queryset.filter(hub_memberships__hub_id__in=hub_ids, hub_memberships__is_active=True)'
new_target = 'queryset = queryset.filter(Q(hub_memberships__hub_id__in=hub_ids, hub_memberships__is_active=True) | Q(hub_id__in=hub_ids))'

assert old_target in content, 'old_target not found'
content = content.replace(old_target, new_target)

open(path, 'w', encoding='utf-8').write(content)
print('Successfully updated SalesAgentListView in apps/sales/views.py')
