!11 <subject> [topic]```\nExample: !11 physics waves",
            inline=False
        )

        embed.add_field(
            name="📗 Get Question for Class 12",
            value="```!12 <subject> [topic]```\nExample: !12 chemistry electrochemistry",
            inline=False
        )

        embed.add_field(
            name="📋 List Available Subjects",
            value="```!subjects```\nShows all subjects you can study",
            inline=False
        )

        creator_info = (
            "```ansi\n"
            "[0;35m┏━━━━━ Creator Information ━━━━━┓[0m\n"
            "[0;36m┃     Made with 💖 by:          ┃[0m\n"
            "[0;33m┃  Rohanpreet Singh Pathania   ┃[0m\n"
            "[0;36m┃     Language: Python 🐍      ┃[0m\n"
            "[0;35m┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛[0m\n"
            "```"
        )

        embed.add_field(
            name="👨‍💻 Credits",
            value=creator_info,
            inline=False
        )

        embed.set_footer(text="Use these commands to practice and learn! 📚✨")
        await ctx.send(embed=embed)

    def _is_question_asked(self, user_id: int, subject: str, question_key: str) -> bool:
        """Check if user has already seen this question"""
        user_questions = self.user_questions.setdefault(user_id, {})
        subject_questions = user_questions.setdefault(subject, set())
        return question_key in subject_questions

    def _mark_question_asked(self, user_id: int, subject: str, question_key: str):
        """Mark a question as asked for a user"""
        user_questions = self.user_questions.setdefault(user_id, {})
        subject_questions = user_questions.setdefault(subject, set())
        subject_questions.add(question_key)

    async def generate_question_with_fallback(self, subject: str, topic: Optional[str], class_num: int) -> Tuple[Dict[str, Any], bool]:
        """Generate a question with fallback to stored questions"""
        if class_num == 11:
            return get_stored_question_11(subject, topic), True
        else:
            return get_stored_question_12(subject, topic), True

    @commands.command(name='11')
    async def class_11(self, ctx, subject: str, topic: Optional[str] = None):
        """Get a question for class 11"""
        if ctx.channel.id != 1337669136729243658:
            await ctx.send("❌ This command can only be used in the designated channel!")
            return

        try:
            subject = subject.lower()
            question, is_fallback = await self.generate_question_with_fallback(subject, topic, 11)

            if question:
                question_key = f"{question['question'][:50]}"
                if self._is_question_asked(ctx.author.id, subject, question_key):
                    await ctx.send("🔄 Finding a new question you haven't seen before...")
                    question, is_fallback = await self.generate_question_with_fallback(subject, topic, 11)

                if question:
                    self._mark_question_asked(ctx.author.id, subject, question_key)
                    await self._send_question(ctx, question, is_fallback)
                else:
                    await ctx.send("❌ Sorry, couldn't find a new question at this time.")
            else:
                await ctx.send("❌ Sorry, I couldn't find a question for that subject/topic.")
        except Exception as e:
            self.logger.error(f"Error in class_11 command: {e}")
            await ctx.send("❌ An error occurred while getting your question.")

    @commands.command(name='12')
    async def class_12(self, ctx, subject: str, topic: Optional[str] = None):
        """Get a question for class 12"""
        if ctx.channel.id != 1337669207193682001:
            await ctx.send("❌ This command can only be used in the designated channel!")
            return

        try:
            subject = subject.lower()
            question, is_fallback = await self.generate_question_with_fallback(subject, topic, 12)

            if question:
                question_key = f"{question['question'][:50]}"
                if self._is_question_asked(ctx.author.id, subject, question_key):
                    await ctx.send("🔄 Finding a new question you haven't seen before...")
                    question, is_fallback = await self.generate_question_with_fallback(subject, topic, 12)

                if question:
                    self._mark_question_asked(ctx.author.id, subject, question_key)
                    await self._send_question(ctx, question, is_fallback)
                else:
                    await ctx.send("❌ Sorry, couldn't find a new question at this time.")
            else:
                await ctx.send("❌ Sorry, I couldn't find a question for that subject/topic.")
        except Exception as e:
            self.logger.error(f"Error in class_12 command: {e}")
            await ctx.send("❌ An error occurred while getting your question.")

    async def _send_question(self, ctx, question: Dict[str, Any], is_fallback: bool = False):
        """Format and send a question"""
        try:
            embed = discord.Embed(
                title="📝 Practice Question",
                description=question['question'],
                color=discord.Color.blue()
            )

            options_text = "\n".join(question['options'])
            embed.add_field(
                name="Options:",
                value=f"```{options_text}```",
                inline=False
            )

            source_text = "📚 From Question Bank" if is_fallback else "🤖 AI Generated"
            embed.add_field(
                name="Source:",
                value=source_text,
                inline=True
            )

            message = await ctx.send(embed=embed)

            explanation_embed = discord.Embed(
                title="📖 Explanation",
                description=f"```{question['explanation']}```",
                color=discord.Color.green()
            )

            explanation_embed.add_field(
                name="Correct Answer:",
                value=f"```Option {question['correct_answer']}