from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from .factories import UserFactory
from .forms import ProfileEditForm, CustomUserCreationForm


class CustomUserModelTest(TestCase):
    """Test CustomUser model"""
    
    def setUp(self):
        self.user = UserFactory()
    
    def test_create_user(self):
        """Test creating user"""
        User = get_user_model()
        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(self.user.is_active)
        self.assertIsNotNone(self.user.username)
        self.assertIsNotNone(self.user.email)
    
    def test_get_full_name(self):
        """Test full name"""
        self.user.first_name = 'John'
        self.user.last_name = 'Doe'
        self.user.save()
        
        self.assertEqual(self.user.get_full_name(), 'John Doe')
    
    def test_wallet_balance(self):
        """Test wallet balance"""
        self.assertEqual(self.user.wallet_balance, 0)
        
        self.user.wallet_balance = 50000
        self.user.save()
        
        self.assertEqual(self.user.wallet_balance, 50000)
    
    def test_phone_number(self):
        """Test phone number"""
        self.user.phone_number = '+989123456789'
        self.user.save()
        
        self.assertIsNotNone(self.user.phone_number)
    
    def test_birth_date(self):
        """Test birth date"""
        self.user.birth_date = '1370/05/15'
        self.user.save()
        
        self.assertEqual(self.user.birth_date, '1370/05/15')
    
    def test_get_tiered_discount(self):
        """Test tiered discount relation"""
        tiered = self.user.get_tiered_discount()
        
        self.assertIsNotNone(tiered)
        self.assertEqual(tiered.user, self.user)
        self.assertEqual(tiered.current_tier, 0)


class ProfileEditFormTest(TestCase):
    """Test ProfileEditForm"""
    
    def setUp(self):
        self.user = UserFactory()
    
    def test_valid_form(self):
        """Test valid form"""
        form_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'phone_number': '+989123456789',
            'birth_date': '1370/05/15',
            'address': 'Test address',
            'postal_code': '12345',
        }
        
        form = ProfileEditForm(data=form_data, instance=self.user)
        
        self.assertTrue(form.is_valid())
    
    def test_invalid_birth_date(self):
        """Test invalid birth date"""
        form_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'phone_number': '+989123456789',
            'birth_date': 'invalid-date',
            'address': 'Test address',
            'postal_code': '12345',
        }
        
        form = ProfileEditForm(data=form_data, instance=self.user)
        
        self.assertFalse(form.is_valid())
        self.assertIn('birth_date', form.errors)
    
    def test_future_birth_date(self):
        """Test future birth date"""
        form_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'phone_number': '+989123456789',
            'birth_date': '1500/01/01',
            'address': 'Test address',
            'postal_code': '12345',
        }
        
        form = ProfileEditForm(data=form_data, instance=self.user)
        
        self.assertFalse(form.is_valid())
        self.assertIn('birth_date', form.errors)
    
    def test_age_over_120(self):
        """Test age over 120"""
        form_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'phone_number': '+989123456789',
            'birth_date': '1200/01/01',
            'address': 'Test address',
            'postal_code': '12345',
        }
        
        form = ProfileEditForm(data=form_data, instance=self.user)
        
        self.assertFalse(form.is_valid())
        self.assertIn('birth_date', form.errors)


class CustomUserCreationFormTest(TestCase):
    """Test CustomUserCreationForm"""
    
    def test_valid_signup(self):
        """Test valid signup"""
        form_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'testpass123',
            'password2': 'testpass123',
        }
        
        form = CustomUserCreationForm(data=form_data)
        
        self.assertTrue(form.is_valid())
    
    def test_password_mismatch(self):
        """Test password mismatch"""
        form_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'testpass123',
            'password2': 'different123',
        }
        
        form = CustomUserCreationForm(data=form_data)
        
        self.assertFalse(form.is_valid())