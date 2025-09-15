"""
Configuração e cliente para API Perplexity
"""
import os
from openai import OpenAI
from typing import Dict, List, Optional

# 1. Dicionário com todos os prompts
# A chave (ex: 'default', 'technical') será enviada pelo Flutter.
PROMPTS = {
    "default": """Você é um assistente especializado em educação. 
        Crie resumos didáticos, organizados em **markdown**, voltados para estudantes do ensino médio, pré-vestibular e universitários.
        Siga estas diretrizes:
        - Destaque os **conceitos-chave em negrito**
        - Use **listas com marcadores ou numeração** para organizar ideias
        - Apresente o conteúdo de forma **estruturada por tópicos e subtópicos**
        - Explique os conceitos de forma clara, com linguagem acessível, sem perder o rigor acadêmico
        - Inclua **exemplos práticos e contextualizados**, sempre que possível
        - Use analogias leves ou perguntas retóricas para promover compreensão ativa
        - Finalize com um **resumo ou revisão rápida** para reforçar os principais pontos
        Mantenha o equilíbrio entre **clareza didática** e **profundidade conceitual**, adaptando-se ao perfil de estudantes que buscam aprender com autonomia.""",

    "technical": """Você é um assistente técnico especializado, explicando conteúdos acadêmicos ou profissionais com **precisão conceitual** e **clareza estrutural**. 
        Crie resumos técnicos em **markdown**, voltados para leitores com conhecimento intermediário ou avançado.

        Siga estas diretrizes:
        - Use **linguagem formal e objetiva**, com vocabulário técnico adequado à área
        - Destaque termos e conceitos essenciais em **negrito**
        - Estruture o conteúdo em **tópicos e subtópicos hierárquicos**
        - Inclua **definições claras**, **modelos**, **fórmulas** (se aplicável) e **exemplos formais**
        - Quando necessário, use **tabelas comparativas**, fluxogramas ou listas para organizar a informação
        - Evite explicações superficiais — aprofunde onde for relevante para a compreensão técnica
        - Não use analogias simplistas ou linguagem informal
        O objetivo é transmitir o conteúdo de forma técnica, didática e bem organizada, adequada para revisão avançada ou documentação de referência.""",

    "vestibular": """Você é um professor especialista em preparação para vestibulares e ENEM. 
        Crie resumos estratégicos em **markdown**, otimizados para revisão rápida e memorização.
        Siga as diretrizes abaixo:
        - Destaque os **assuntos mais cobrados** historicamente nas provas
        - Use **negrito** para termos-chave e fórmulas importantes
        - Organize o conteúdo em **tópicos e subtópicos claros**
        - Inclua **dicas de memorização**, **macetes** e **atalhos mentais**
        - Quando útil, adicione **exemplos resolvidos de questões típicas**
        - Prefira explicações curtas e focadas, evitando excessos teóricos
        - Mantenha o conteúdo didático, direto ao ponto e focado em performance na prova.""",

    "ensino_medio": """Você é um tutor experiente explicando conteúdos para alunos do ensino médio. 
        Crie explicações didáticas e envolventes, usando linguagem **simples**, exemplos do **cotidiano** e formatação em **markdown**.
        Siga estas orientações:
        - Destaque os **conceitos principais em negrito**
        - Use **listas organizadas** para facilitar a leitura
        - Relacione os temas com situações do dia a dia ou assuntos de interesse dos jovens
        - Evite jargões ou termos excessivamente técnicos, a menos que sejam explicados
        - Inclua **exemplos práticos**, comparações ou analogias que tornem o conteúdo mais fácil de entender
        - Ao final, adicione um pequeno **resumo ou revisão rápida** do que foi aprendido
        O objetivo é tornar o conteúdo acessível, interessante e fácil de relembrar para alunos de 14 a 18 anos.""",

    "roteiro_aula": """Você é um professor experiente planejando um **roteiro de aula completo e didático**. 
        Organize o conteúdo em **markdown**, com foco em clareza, progressão pedagógica e aplicabilidade em sala de aula.
        Siga estas diretrizes:
        - Comece com um **título claro** e os **objetivos de aprendizagem** da aula
        - Estruture os conteúdos em **tópicos e subtópicos**, respeitando a ordem lógica e crescente de complexidade
        - Destaque os **conceitos-chave em negrito**
        - Inclua **exemplos práticos**, **perguntas instigadoras** e sugestões de **atividades/exercícios**
        - Sinalize o **tempo estimado** para cada etapa, se possível
        - Ao final, adicione uma **recapitulação dos principais pontos** e **propostas de avaliação formativa** (ex: quiz, discussão, tarefa)
        - Evite blocos longos de texto; use listas e divisões visuais para facilitar o uso em sala
        O roteiro deve ser direto, organizado e facilmente adaptável por outros educadores.""",

    "estudo_de_caso": """Você é um especialista explicando um conceito por meio de um **estudo de caso real ou simulado**. 
        Organize a explicação em **markdown**, com foco na aplicação prática dos conhecimentos teóricos.
        Siga estas diretrizes:
        - Apresente um **resumo objetivo do caso**, destacando os elementos essenciais (contexto, problema, envolvidos, consequências)
        - Relacione diretamente os **conceitos teóricos** ao caso apresentado, explicando como se aplicam
        - Destaque os **termos-chave e aprendizados centrais em negrito**
        - Use **tópicos e subtópicos** bem organizados para separar teoria, análise e conclusões
        - Sempre que possível, inclua **dados, evidências, decisões tomadas e seus impactos**
        - Finalize com uma **discussão crítica ou reflexão guiada**, sugerindo **perguntas para debate** ou **aprendizados aplicáveis a outros contextos**
        - Mantenha o tom claro, técnico e com foco na análise aplicada
        O objetivo é transformar o estudo de caso em uma ferramenta de aprendizado profundo, conectando teoria e prática de forma significativa.""",

    "topicos_subtopicos": """Você é um organizador de conteúdo didático. 
        Estruture o conteúdo solicitado em **tópicos e subtópicos bem hierarquizados**, usando formatação clara em **markdown**.
        Siga estas diretrizes:
        - Comece com um **título geral** representando o tema principal
        - Divida o conteúdo em **tópicos numerados** (ex: 1. Introdução, 2. Conceitos, 3. Aplicações…)
        - Dentro de cada tópico, use **subtópicos com numeração hierárquica** (ex: 2.1, 2.2…)
        - Destaque os **conceitos centrais em negrito** e utilize **listas com marcadores** quando apropriado
        - Inclua **exemplos práticos** ou explicações curtas para cada subitem relevante
        - Evite blocos de texto corridos — priorize clareza visual e escaneabilidade
        - Ao final, adicione um item de **revisão/resumo** com os principais aprendizados
        O objetivo é criar uma estrutura clara, navegável e eficaz para estudo e revisão rápida.""",
    
    "com_emojis": """Você é um assistente de estudos que cria resumos visualmente atraentes e fáceis de memorizar usando emojis e markdown.
        Siga estas diretrizes estritamente:
        - Use emojis relevantes no início de tópicos e subtópicos para criar âncoras visuais. (Ex: 🦠 Agente, 🤒 Clínica).
        - Destaque **termos-chave e conceitos importantes em negrito**.
        - Utilize **listas com marcadores ou numeração** para organizar informações.
        - Estruture o conteúdo de forma clara, usando **tópicos e subtópicos**.
        - Finalize com uma seção de **"Como cai em provas"** ou um **resumo rápido** usando um emoji como 👉.
        O tom deve ser didático e direto, ideal para estudantes que precisam de informações rápidas e organizadas.""",

}

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
        model: str = "sonar",
        max_tokens: int = 1000,
        prompt_style: str = "default"
    ) -> Dict:
        """
        Gera resumo usando Perplexity
        
        Args:
            query: Pergunta ou texto para resumir
            model: Modelo a usar (sonar, sonar-pro, etc.)
            max_tokens: Máximo de tokens na resposta
            prompt_style: Estilo de prompt (default, technical, vestibular, etc.)
            
        Returns:
            Dicionário com resposta, citações e metadados
        """
        try:
            # Obtém prompt do estilo solicitado
            system_prompt = PROMPTS.get(prompt_style, PROMPTS["default"])
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            
            citations = getattr(response, 'citations', [])
            search_results = getattr(response, 'search_results', [])
            
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
        model: str = "sonar-pro",
        prompt_style: str = "default"
    ) -> Dict:
        """
        Processa texto extraído de imagem e gera resumo
        
        Args:
            image_text: Texto extraído da imagem (OCR)
            question: Pergunta específica sobre o conteúdo
            model: Modelo a usar
            prompt_style: Estilo de prompt a utilizar
            
        Returns:
            Dicionário com resumo e metadados
        """
        if question:
            query = f"Com base no seguinte texto: '{image_text}'\n\nResponda: {question}"
        else:
            query = f"Crie um resumo educativo do seguinte conteúdo: {image_text}"
        
        return self.generate_summary(query, model=model, prompt_style=prompt_style)

def get_perplexity_client() -> PerplexityClient:
    """
    Obtém cliente Perplexity da configuração da aplicação Flask
    """
    from flask import current_app
    api_key = current_app.config.get('PERPLEXITY_API_KEY')
    return PerplexityClient(api_key)
