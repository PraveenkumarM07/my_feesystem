from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vemu_fee.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'student_login'

# Database Models
class Student(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    total_fee = db.Column(db.Float, default=0.0)
    paid_fee = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    transactions = db.relationship('Transaction', backref='student', lazy=True)
    complaints = db.relationship('Complaint', backref='student', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    transaction_id = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')  # open, in_progress, resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(int(user_id))

# Routes
@app.route('/')
def main():
    """Main landing page"""
    return render_template('main.html')

@app.route('/studentlogin')
def student_login_page():
    """Student login page"""
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def student_login():
    """Handle student login"""
    try:
        data = request.get_json()
        roll_number = data.get('rollNumber')
        password = data.get('password')
        
        if not roll_number or not password:
            return jsonify({'success': False, 'message': 'Roll number and password are required'}), 400
        
        student = Student.query.filter_by(roll_number=roll_number).first()
        
        if student and check_password_hash(student.password_hash, password):
            login_user(student)
            return jsonify({
                'success': True, 
                'message': 'Login successful',
                'student': {
                    'id': student.id,
                    'name': student.name,
                    'roll_number': student.roll_number,
                    'department': student.department,
                    'year': student.year,
                    'total_fee': student.total_fee,
                    'paid_fee': student.paid_fee,
                    'balance': student.total_fee - student.paid_fee
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Invalid roll number or password'}), 401
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Login error: {str(e)}'}), 500

@app.route('/api/logout')
@login_required
def logout():
    """Handle student logout"""
    logout_user()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/student/profile')
@login_required
def get_student_profile():
    """Get current student profile"""
    try:
        student = current_user
        return jsonify({
            'success': True,
            'student': {
                'id': student.id,
                'name': student.name,
                'roll_number': student.roll_number,
                'email': student.email,
                'department': student.department,
                'year': student.year,
                'total_fee': student.total_fee,
                'paid_fee': student.paid_fee,
                'balance': student.total_fee - student.paid_fee
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching profile: {str(e)}'}), 500

@app.route('/api/transactions', methods=['GET'])
@login_required
def get_transactions():
    """Get student transactions"""
    try:
        transactions = Transaction.query.filter_by(student_id=current_user.id).order_by(Transaction.created_at.desc()).all()
        transaction_list = []
        
        for trans in transactions:
            transaction_list.append({
                'id': trans.id,
                'amount': trans.amount,
                'payment_method': trans.payment_method,
                'transaction_id': trans.transaction_id,
                'status': trans.status,
                'created_at': trans.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'description': trans.description
            })
        
        return jsonify({'success': True, 'transactions': transaction_list})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching transactions: {str(e)}'}), 500

@app.route('/api/transactions', methods=['POST'])
@login_required
def submit_transaction():
    """Submit a new transaction"""
    try:
        data = request.get_json()
        amount = data.get('amount')
        payment_method = data.get('paymentMethod')
        description = data.get('description', '')
        
        if not amount or not payment_method:
            return jsonify({'success': False, 'message': 'Amount and payment method are required'}), 400
        
        # Generate unique transaction ID
        import uuid
        transaction_id = str(uuid.uuid4())
        
        # Create new transaction
        transaction = Transaction(
            student_id=current_user.id,
            amount=float(amount),
            payment_method=payment_method,
            transaction_id=transaction_id,
            description=description,
            status='pending'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Transaction submitted successfully',
            'transaction': {
                'id': transaction.id,
                'transaction_id': transaction_id,
                'amount': transaction.amount,
                'payment_method': transaction.payment_method,
                'status': transaction.status
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error submitting transaction: {str(e)}'}), 500

@app.route('/api/complaints', methods=['GET'])
@login_required
def get_complaints():
    """Get student complaints"""
    try:
        complaints = Complaint.query.filter_by(student_id=current_user.id).order_by(Complaint.created_at.desc()).all()
        complaint_list = []
        
        for complaint in complaints:
            complaint_list.append({
                'id': complaint.id,
                'subject': complaint.subject,
                'message': complaint.message,
                'status': complaint.status,
                'created_at': complaint.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'resolved_at': complaint.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if complaint.resolved_at else None
            })
        
        return jsonify({'success': True, 'complaints': complaint_list})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching complaints: {str(e)}'}), 500

@app.route('/api/complaints', methods=['POST'])
@login_required
def submit_complaint():
    """Submit a new complaint"""
    try:
        data = request.get_json()
        subject = data.get('subject')
        message = data.get('message')
        
        if not subject or not message:
            return jsonify({'success': False, 'message': 'Subject and message are required'}), 400
        
        # Create new complaint
        complaint = Complaint(
            student_id=current_user.id,
            subject=subject,
            message=message,
            status='open'
        )
        
        db.session.add(complaint)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Complaint submitted successfully',
            'complaint': {
                'id': complaint.id,
                'subject': complaint.subject,
                'status': complaint.status
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error submitting complaint: {str(e)}'}), 500

@app.route('/api/search/student/<roll_number>')
def search_student(roll_number):
    """Search for a student by roll number (public endpoint)"""
    try:
        student = Student.query.filter_by(roll_number=roll_number).first()
        
        if student:
            return jsonify({
                'success': True,
                'student': {
                    'name': student.name,
                    'roll_number': student.roll_number,
                    'department': student.department,
                    'year': student.year
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error searching student: {str(e)}'}), 500

@app.route('/api/student/balance')
@login_required
def get_balance():
    """Get current student's fee balance"""
    try:
        student = current_user
        balance = student.total_fee - student.paid_fee
        
        return jsonify({
            'success': True,
            'balance': balance,
            'total_fee': student.total_fee,
            'paid_fee': student.paid_fee
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching balance: {str(e)}'}), 500

# Admin routes for managing data
@app.route('/admin/init-db')
def init_database():
    """Initialize database with sample data"""
    try:
        # Create tables
        db.create_all()
        
        # Check if sample data already exists
        if Student.query.first():
            return jsonify({'message': 'Database already initialized'})
        
        # Create sample students
        sample_students = [
            {
                'roll_number': '2021001',
                'name': 'John Doe',
                'email': 'john.doe@vemu.edu',
                'password': 'password123',
                'department': 'Computer Science',
                'year': 2,
                'total_fee': 50000.0,
                'paid_fee': 30000.0
            },
            {
                'roll_number': '2021002',
                'name': 'Jane Smith',
                'email': 'jane.smith@vemu.edu',
                'password': 'password123',
                'department': 'Electrical Engineering',
                'year': 3,
                'total_fee': 60000.0,
                'paid_fee': 45000.0
            },
            {
                'roll_number': '2021003',
                'name': 'Mike Johnson',
                'email': 'mike.johnson@vemu.edu',
                'password': 'password123',
                'department': 'Mechanical Engineering',
                'year': 1,
                'total_fee': 40000.0,
                'paid_fee': 20000.0
            }
        ]
        
        for student_data in sample_students:
            student = Student(
                roll_number=student_data['roll_number'],
                name=student_data['name'],
                email=student_data['email'],
                password_hash=generate_password_hash(student_data['password']),
                department=student_data['department'],
                year=student_data['year'],
                total_fee=student_data['total_fee'],
                paid_fee=student_data['paid_fee']
            )
            db.session.add(student)
        
        db.session.commit()
        
        return jsonify({'message': 'Database initialized successfully with sample data'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error initializing database: {str(e)}'}), 500

@app.route('/admin/update-fee/<int:student_id>', methods=['POST'])
def update_student_fee(student_id):
    """Update student fee payment (admin function)"""
    try:
        data = request.get_json()
        amount = data.get('amount')
        
        if not amount:
            return jsonify({'error': 'Amount is required'}), 400
        
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        # Update paid fee
        student.paid_fee += float(amount)
        
        # Create transaction record
        import uuid
        transaction = Transaction(
            student_id=student.id,
            amount=float(amount),
            payment_method='admin_update',
            transaction_id=str(uuid.uuid4()),
            status='completed',
            description='Fee payment updated by admin'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'message': 'Fee updated successfully',
            'new_balance': student.total_fee - student.paid_fee
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error updating fee: {str(e)}'}), 500

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Page not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000) 