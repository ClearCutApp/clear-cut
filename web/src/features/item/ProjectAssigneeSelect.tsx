import { useEffect, useState } from "react";
import { getProjectMembers, type ProjectMembers } from "../../api/client";
import { useAuth } from "../../state/AuthContext";
import { useLocale } from "../../state/LocaleContext";

export function ProjectAssigneeSelect({ projectId, value, onChange }: {
  projectId: string; value: string; onChange: (value: string) => void;
}) {
  const { text } = useLocale();
  const { user } = useAuth();
  const [members, setMembers] = useState<ProjectMembers["members"] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    void getProjectMembers(projectId).then(value => { if (active) setMembers(value.members); })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [projectId]);
  return <div><label>{text("Assigned to", "Asignado a")}<select value={value} disabled={members === null} onChange={event => onChange(event.target.value)}>
    <option value="">{text("Unassigned", "Sin asignar")}</option>
    {value && !members?.some(member => member.user_id === value) && <option value={value}>{value}</option>}
    {members?.map(member => <option key={member.user_id} value={member.user_id}>{member.user_id === user?.uid ? text("You", "Tú") : member.email || member.user_id}</option>)}
  </select></label>{failed && <p>{text("The project member list is unavailable. Existing assignment is preserved.", "La lista del equipo del proyecto no está disponible. La asignación existente se conserva.")}</p>}</div>;
}
