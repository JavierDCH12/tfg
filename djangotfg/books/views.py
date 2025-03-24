from django.views.decorators.cache import cache_page
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import requests

@cache_page(60)  # Usamos el decorador cache_page de DRF
@api_view(['GET'])
@permission_classes([AllowAny])

def search_books(request):
    title = request.GET.get('title', '')
    author = request.GET.get('author', '')
    genre = request.GET.get('genre', '')
    page = int(request.GET.get('page', 1))
    per_page = 20  # Queremos mostrar 20 resultados por página
    max_results = 60  # Limitar el total a 60 resultados

    if not (title or author or genre):
        return Response({"detail": "Debes proporcionar al menos un parámetro (title, author o genre)"},
                        status=status.HTTP_400_BAD_REQUEST)

    query_parts = []
    if title:
        query_parts.append(f"title:{title}")
    if author:
        query_parts.append(f"author:{author}")
    if genre:
        query_parts.append(f"subject:{genre}")

    query = "+".join(query_parts)
    offset = (page - 1) * per_page
    url = f'https://openlibrary.org/search.json?q={query}&limit={per_page}&offset={offset}'

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        resultados = []

        # Limitar a 60 resultados
        for book in data.get('docs', [])[:max_results]:
            title = book.get('title', 'Desconocido')
            author = ", ".join(book.get('author_name', ['Desconocido'])[:3])
            genres = [", ".join(book.get('subject', [])[:3])] if book.get('subject') else None

            openlibrary_key = book.get('key', '')
            if openlibrary_key.startswith("/works/"):
                book_key = openlibrary_key.replace("/works/", "")
            else:
                book_key = "UNKNOWN"

            book_info = {
                'title': title,
                'author': author,
                'first_publish_year': book.get('first_publish_year'),
                'isbn': book.get('isbn', [None])[0],
                'genres': genres,
                'book_key': book_key,
                'cover_url': f"https://covers.openlibrary.org/b/id/{book['cover_i']}-M.jpg" if book.get(
                    'cover_i') else None
            }
            resultados.append(book_info)

        total_pages = 3  # Queremos mostrar solo 3 páginas con un máximo de 60 resultados
        return Response({
            "books": resultados,
            "total_count": len(resultados),
            "total_pages": total_pages
        }, status=status.HTTP_200_OK)

    return Response({"detail": "Error en la consulta a OpenLibrary"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@cache_page(60)
@api_view(['GET'])
def get_book_description(request, book_key):
    """
    Obtiene la descripción de un libro usando su `key` en Open Library.
    """
    url = f'https://openlibrary.org{book_key}.json'  # 🔥 Consultamos la API con el key
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        description = data.get('description', 'No description available')

        # Si la descripción es un diccionario, extraemos el texto
        if isinstance(description, dict):
            description = description.get('value', 'No description available')

        return Response({'description': description}, status=status.HTTP_200_OK)

    return Response({"detail": "No se encontró la descripción"}, status=status.HTTP_404_NOT_FOUND)


@cache_page(60)
@api_view(['GET'])
@permission_classes([AllowAny])
def get_book_details(request, book_key):
    url = f'https://openlibrary.org/works/{book_key}.json'

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()

        # Título y descripción
        title = data.get('title', 'Unknown title')
        description = data.get('description', {})
        if isinstance(description, dict):
            description = description.get('value', 'No description available.')
        elif isinstance(description, str):
            description = description
        else:
            description = 'No description available.'

        # Autores (requiere segunda consulta)
        authors_data = data.get('authors', [])
        authors = []
        for author_ref in authors_data:
            author_key = author_ref.get('author', {}).get('key')
            if author_key:
                author_response = requests.get(f'https://openlibrary.org{author_key}.json')
                if author_response.status_code == 200:
                    author_name = author_response.json().get('name')
                    if author_name:
                        authors.append(author_name)

        # Portada
        cover_id = data.get('covers', [None])[0]
        cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None

        # Año de publicación (fecha de creación)
        publish_year = data.get('created', {}).get('value', '')[:4] if data.get('created') else None

        # Géneros
        subjects = data.get('subjects', [])[:3] if data.get('subjects') else None

        book_info = {
            'title': title,
            'description': description,
            'authors': authors,
            'cover_url': cover_url,
            'first_publish_year': publish_year,
            'genres': subjects,
            'book_key': book_key,
        }

        return Response(book_info, status=status.HTTP_200_OK)

    return Response({"detail": "Book not found"}, status=status.HTTP_404_NOT_FOUND)
