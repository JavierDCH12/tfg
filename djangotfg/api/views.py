from django.db.models import Count
from django.views.decorators.cache import cache_page
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView

from constants import SUCCESS_DEACTIVATE, ERROR_REGISTER, SUCCESS_UPDATE_PROFILE, ERROR_FETCHING_FAVS, \
    INFO_ALREADY_FAVS, INFO_BOOK_REMOVED_FAVS, ERROR_BOOK_NOT_FOUND_IN_FAVS, ERROR_UPLOAD_PHOTO, \
    SUCCESS_UPLOAD_PHOTO, ERROR_EMPTY, SUCCESS_SAVED_REVIEW, ERROR_INVALID_REVIEW, SUCCESS_UPDATE_REVIEW, \
    ERROR_USER_NOT_FOUND
from .models import FavoriteBook
from .notifications.email import send_welcome_email
from .security.throttles import LoginRateThrottle, RegisterRateThrottle, FavoriteRateThrottle, ProfileUpdateRateThrottle
from .serializers import UserProfileSerializer, RegisterSerializer, FavoriteBookSerializer, PublicUserProfileSerializer
from django.contrib.auth import get_user_model
import logging

# Configuración de logs
logger = logging.getLogger(__name__)

User = get_user_model()

class CustomLoginView(TokenObtainPairView):
    @throttle_classes([LoginRateThrottle])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)




### ✅ OBTENER TODOS LOS USUARIOS (Solo si es necesario)
@cache_page(60)  # Cache de 1 minuto
@api_view(['GET'])
def get_all_users(request):
    """Retrieve all users."""
    users = User.objects.all()
    serializer = UserProfileSerializer(users, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


### ✅ PERFIL DE USUARIO (GET & DELETE)
@api_view(['GET', 'DELETE'])
@cache_page(60)
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Retrieve or deactivate user profile."""
    user = request.user

    if request.method == 'DELETE':
        user.is_active = False
        user.save()
        return Response({'detail': SUCCESS_DEACTIVATE}, status=status.HTTP_204_NO_CONTENT)

    elif request.method == 'GET':
        serializer = UserProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


### ✅ REGISTRO DE USUARIO
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegisterRateThrottle])
def register_user(request):
    """Registers a new user."""
    serializer = RegisterSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        send_welcome_email(request.data.get('email'), request.data.get('username'))
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    logger.error(ERROR_REGISTER, {serializer.errors})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



### UPDATE PROFILE

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@throttle_classes([ProfileUpdateRateThrottle])
def update_profile(request):
    """Permite a los usuarios actualizar su perfil (nombre, apellidos, contraseña)."""
    user = request.user
    serializer = UserProfileSerializer(user, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()
        return Response({"message": SUCCESS_UPDATE_PROFILE, "user": serializer.data}, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)





### ✅ OBTENER FAVORITOS (GET) & AÑADIR FAVORITO (POST)
@api_view(['GET', 'POST'])
@cache_page(60)
@permission_classes([IsAuthenticated])
@throttle_classes([FavoriteRateThrottle])
def manage_favorites(request):
    """Handles retrieving and adding favorite books."""
    user = request.user

    if request.method == 'GET':
        try:
            favorites = FavoriteBook.objects.filter(user=request.user).order_by('-id')
            paginator = PageNumberPagination()
            paginator.page_size = 10
            result_page = paginator.paginate_queryset(favorites, request)
            serialized_data = FavoriteBookSerializer(result_page, many=True).data
            return paginator.get_paginated_response(serialized_data)

        except Exception as e:
            logger.error(f"❌ Error fetching favorites: {str(e)}")
            return Response({"error": ERROR_FETCHING_FAVS}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    elif request.method == 'POST':
        serializer = FavoriteBookSerializer(data=request.data)

        if serializer.is_valid():
            book_key = serializer.validated_data.get('book_key')

            if FavoriteBook.objects.filter(user=user, book_key=book_key).exists():
                logger.warning(f"⚠️ Book {book_key} is already in favorites for user {user.username}")
                return Response({'message': INFO_ALREADY_FAVS}, status=status.HTTP_400_BAD_REQUEST)

            serializer.save(user=user)
            logger.info(f"✅ Book {book_key} added to favorites for user {user.username}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        logger.error(f"❌ Error adding favorite: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)






### ✅ ELIMINAR UN FAVORITO
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_favorite(request, book_key):
    """Remove a favorite book from the user's list."""
    user = request.user
    favorite = FavoriteBook.objects.filter(user=user, book_key=book_key).first()

    if favorite:
        favorite.delete()
        logger.info(f"✅ Book {book_key} removed from favorites for user {user.username}")
        return Response({'message': INFO_BOOK_REMOVED_FAVS}, status=status.HTTP_204_NO_CONTENT)

    logger.warning(f"⚠️ Book {book_key} not found in favorites for user {user.username}")
    return Response({'message': ERROR_BOOK_NOT_FOUND_IN_FAVS}, status=status.HTTP_404_NOT_FOUND)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_profile_picture(request):
    """Subir o actualizar la foto de perfil del usuario"""
    user = request.user

    if 'profile_picture' not in request.FILES:
        return Response({"error": ERROR_UPLOAD_PHOTO}, status=status.HTTP_400_BAD_REQUEST)

    user.profile_picture = request.FILES['profile_picture']
    user.save()

    return Response(
        {
            "message": SUCCESS_UPLOAD_PHOTO,
            "profile_picture": user.profile_picture.url
        },
        status=status.HTTP_200_OK
    )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def manage_review(request, book_key):
    """Crea o actualiza la reseña de un libro favorito"""
    user = request.user
    favorite = FavoriteBook.objects.filter(user=user, book_key=book_key).first()

    if not favorite:
        return Response({'error': ERROR_BOOK_NOT_FOUND_IN_FAVS}, status=status.HTTP_404_NOT_FOUND)

    review_text = request.data.get('review', '').strip()

    if not review_text:
        return Response({'error': ERROR_EMPTY}, status=status.HTTP_400_BAD_REQUEST)

    favorite.review = review_text  # Si es nuevo, lo asigna; si ya existe, lo sobrescribe.
    favorite.save()

    return Response({'message': SUCCESS_SAVED_REVIEW, 'review': favorite.review}, status=status.HTTP_200_OK)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_rating(request, book_key):
    user = request.user
    favorite = FavoriteBook.objects.filter(user=user, book_key=book_key).first()

    if not favorite:
        return Response({'error': ERROR_BOOK_NOT_FOUND_IN_FAVS}, status=status.HTTP_404_NOT_FOUND)

    rating_value = request.data.get('rating')
    try:
        rating_value = int(rating_value)
        if rating_value < 0 or rating_value > 5:
            raise ValueError
    except (ValueError, TypeError):
        return Response({'error': ERROR_INVALID_REVIEW}, status=status.HTTP_400_BAD_REQUEST)

    favorite.rating = rating_value
    favorite.save()

    return Response({'message': SUCCESS_UPDATE_REVIEW, 'rating': favorite.rating})


@api_view(['GET'])
@permission_classes([AllowAny])
def public_profile_view(request, username):
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response({'error': ERROR_USER_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

    serializer = PublicUserProfileSerializer(user)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def popular_books(request):
    """Devuelve los libros más populares basados en favoritos de usuarios"""
    top_books = (
        FavoriteBook.objects.values(
            'book_key', 'title', 'author', 'cover_url', 'first_publish_year'
        )
        .annotate(favorites_count=Count('id'))
        .order_by('-favorites_count')[:20]
    )

    return Response(list(top_books), status=status.HTTP_200_OK)