"""
Configuração e cliente para API Perplexity
"""
import os
from openai import OpenAI
from typing import Dict, List, Optional

class PerplexityClient:
    """Cliente para interagir com a API Perplexity"""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("PERPLEXITY_API_KEY é obrigatório")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai"
        )
    
    def generate_summary(
        self, 
        query: str, 
        model: str = "sonar-pro",
        max_tokens: int = 1000
    ) -> Dict:
        """
        Gera resumo usando Perplexity
        
        Args:
            query: Pergunta ou texto para resumir
            model: Modelo a usar (sonar, sonar-pro, etc.)
            max_tokens: Máximo de tokens na resposta
            
        Returns:
            Dicionário com resposta, citações e metadados
        """
        try:
            # Prompt otimizado para estudos
            system_prompt = """Você é um assistente especializado em educação. 
            Crie resumos claros e estruturados em markdown para estudantes.
            Inclua:
            - Conceitos principais em negrito
            - Listas organizadas quando apropriado
            - Explicações didáticas
            - Exemplos práticos quando relevante
            
            Mantenha o conteúdo acadêmico mas acessível."""
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                max_tokens=max_tokens,
                temperature=0.3  # Mais determinístico para conteúdo educacional
            )
            
            # Extrair informações da resposta
            content = response.choices[0].message.content
            
            # Extrair citações se disponíveis
            citations = []
            if hasattr(response, 'citations') and response.citations:
                citations = response.citations
            
            # Extrair resultados de busca se disponíveis
            search_results = []
            if hasattr(response, 'search_results') and response.search_results:
                search_results = response.search_results
            
            return {
                "content": content,
                "citations": citations,
                "search_results": search_results,
                "model_used": model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "success": True
            }
            
        except Exception as e:
            return {
                "content": "",
                "citations": [],
                "search_results": [],
                "model_used": model,
                "tokens_used": 0,
                "success": False,
                "error": str(e)
            }
    
    def process_image_query(
        self, 
        image_text: str, 
        question: str = None,
        model: str = "sonar-pro"
    ) -> Dict:
        """
        Processa texto extraído de imagem e gera resumo
        
        Args:
            image_text: Texto extraído da imagem (OCR)
            question: Pergunta específica sobre o conteúdo
            model: Modelo a usar
            
        Returns:
            Dicionário com resumo e metadados
        """
        if question:
            query = f"Com base no seguinte texto: '{image_text}'\n\nResponda: {question}"
        else:
            query = f"Crie um resumo educativo do seguinte conteúdo: {image_text}"
        
        return self.generate_summary(query, model)

def get_perplexity_client() -> PerplexityClient:
    """
    Obtém cliente Perplexity da configuração da aplicação Flask
    """
    from flask import current_app
    api_key = current_app.config.get('PERPLEXITY_API_KEY')
    return PerplexityClient(api_key)

