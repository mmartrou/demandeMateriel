// Script de la page students (extrait de templates/students.html).
let students = [];

// Load students on page load
document.addEventListener('DOMContentLoaded', function() {
    loadStudents();
});

async function loadStudents() {
    try {
        const response = await fetch('/api/students');
        students = await response.json();
        displayStudents();
    } catch (error) {
        console.error('Erreur lors du chargement des effectifs:', error);
        alert('Erreur lors du chargement des effectifs');
    }
}

function displayStudents() {
    const tbody = document.getElementById('studentsTableBody');
    tbody.innerHTML = '';
    
    students.forEach(student => {
        const row = `
            <tr>
                <td><strong>${student.teacher_name}</strong></td>
                <td><span class="badge bg-primary">${student.level}</span></td>
                <td><span class="badge bg-info fs-6">${student.student_count} élèves</span></td>
                <td>
                    <button class="btn btn-sm btn-primary me-2" onclick="editStudent(${student.id})">
                        <i class="fas fa-edit"></i> Modifier
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="confirmDeleteStudent(${student.id})">
                        <i class="fas fa-trash"></i> Supprimer
                    </button>
                </td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}

function editStudent(studentId) {
    const student = students.find(s => s.id === studentId);
    if (!student) return;
    
    document.getElementById('editStudentId').value = student.id;
    document.getElementById('editTeacherName').value = student.teacher_name;
    document.getElementById('editLevel').value = student.level;
    document.getElementById('editStudentCount').value = student.student_count;
    
    new bootstrap.Modal(document.getElementById('editStudentModal')).show();
}

async function addStudent() {
    try {
        const studentData = {
            teacher_name: document.getElementById('addTeacherName').value,
            level: document.getElementById('addLevel').value,
            student_count: parseInt(document.getElementById('addStudentCount').value)
        };
        
        const response = await fetch('/api/students', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(studentData)
        });
        
        if (response.ok) {
            bootstrap.Modal.getInstance(document.getElementById('addStudentModal')).hide();
            document.getElementById('addStudentForm').reset();
            loadStudents();
            alert('Effectif ajouté avec succès');
        } else {
            const error = await response.json();
            alert('Erreur: ' + error.error);
        }
    } catch (error) {
        console.error('Erreur:', error);
        alert('Erreur lors de l\'ajout');
    }
}

async function saveStudent() {
    try {
        const studentId = document.getElementById('editStudentId').value;
        const studentData = {
            teacher_name: document.getElementById('editTeacherName').value,
            level: document.getElementById('editLevel').value,
            student_count: parseInt(document.getElementById('editStudentCount').value)
        };
        
        const response = await fetch(`/api/students/${studentId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(studentData)
        });
        
        if (response.ok) {
            bootstrap.Modal.getInstance(document.getElementById('editStudentModal')).hide();
            loadStudents();
            alert('Effectif mis à jour avec succès');
        } else {
            const error = await response.json();
            alert('Erreur: ' + error.error);
        }
    } catch (error) {
        console.error('Erreur:', error);
        alert('Erreur lors de la sauvegarde');
    }
}

function confirmDeleteStudent(studentId) {
    const student = students.find(s => s.id === studentId);
    if (!student) return;
    
    if (confirm(`Êtes-vous sûr de vouloir supprimer l'effectif de ${student.teacher_name} (${student.level}) ?`)) {
        deleteStudentById(studentId);
    }
}

async function deleteStudent() {
    const studentId = document.getElementById('editStudentId').value;
    if (confirm('Êtes-vous sûr de vouloir supprimer cet effectif ?')) {
        await deleteStudentById(studentId);
        bootstrap.Modal.getInstance(document.getElementById('editStudentModal')).hide();
    }
}

async function deleteStudentById(studentId) {
    try {
        const response = await fetch(`/api/students/${studentId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadStudents();
            alert('Effectif supprimé avec succès');
        } else {
            const error = await response.json();
            alert('Erreur: ' + error.error);
        }
    } catch (error) {
        console.error('Erreur:', error);
        alert('Erreur lors de la suppression');
    }
}
